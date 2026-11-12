# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.constrains("product_qty", "product_uom")
    def _check_contract_quantities(self):
        for line in self:
            contract_lines = self.env["contract.line"].search(
                [
                    ("purchase_line_id", "=", line.id),
                    ("is_canceled", "=", False),
                ]
            )
            total_quantity = sum(
                contract_line.uom_id._compute_quantity(
                    contract_line.quantity,
                    line.product_uom,
                    round=False,
                )
                for contract_line in contract_lines
            )
            if (
                float_compare(
                    total_quantity,
                    line.product_qty,
                    precision_rounding=line.product_uom.rounding,
                )
                > 0
            ):
                raise ValidationError(
                    self.env._(
                        "The quantity ordered for product '%s' "
                        "cannot be less than the total contracted quantity."
                    )
                    % line.product_id.display_name
                )
