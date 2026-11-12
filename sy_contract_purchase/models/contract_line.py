# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ContractLine(models.Model):
    _inherit = "contract.line"

    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Purchase Order Line",
        index=True,
        copy=False,
        ondelete="set null",
    )

    @api.constrains(
        "purchase_line_id",
        "quantity",
        "uom_id",
        "is_canceled",
    )
    def _check_purchase_line_quantity(self):
        for line in self.filtered(lambda record: record.purchase_line_id):
            purchase_line = line.purchase_line_id
            contract_lines = self.search(
                [
                    ("purchase_line_id", "=", purchase_line.id),
                    ("is_canceled", "=", False),
                ]
            )
            total_quantity = sum(
                contract_line.uom_id._compute_quantity(
                    contract_line.quantity,
                    purchase_line.product_uom,
                    round=False,
                )
                for contract_line in contract_lines
            )
            if (
                float_compare(
                    total_quantity,
                    purchase_line.product_qty,
                    precision_rounding=purchase_line.product_uom.rounding,
                )
                > 0
            ):
                raise ValidationError(
                    self.env._(
                        "The total contracted quantity for product '%s' "
                        "cannot exceed the quantity ordered."
                    )
                    % purchase_line.product_id.display_name
                )
