# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ContractPurchaseWizardLine(models.TransientModel):
    _name = "contract.purchase.wizard.line"
    _description = "Generate Purchase Contract Wizard Line"

    wizard_id = fields.Many2one(
        comodel_name="contract.purchase.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Purchase Order Line",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
        readonly=True,
    )
    name = fields.Text(
        string="Description",
        required=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        required=True,
        readonly=True,
    )
    available_quantity = fields.Float(
        readonly=True,
    )
    quantity = fields.Float(
        required=True,
    )
    price_unit = fields.Float(
        string="Unit Price",
    )

    @api.constrains("quantity", "available_quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(
                    self.env._("The quantity must be greater than zero.")
                )
            if line.quantity > line.available_quantity:
                raise ValidationError(
                    self.env._("The quantity cannot exceed the available quantity.")
                )
