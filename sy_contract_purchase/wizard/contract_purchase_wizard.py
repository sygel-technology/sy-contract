# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ContractPurchaseWizard(models.TransientModel):
    _name = "contract.purchase.wizard"
    _description = "Generate Purchase Contract Wizard"

    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
    )
    name = fields.Char(
        string="Contract Name",
        required=True,
    )
    date_start = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.context_today,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible",
        default=lambda self: self.env.user,
    )
    line_ids = fields.One2many(
        comodel_name="contract.purchase.wizard.line",
        inverse_name="wizard_id",
        string="Contract Lines",
    )
    recurring_rule_type = fields.Selection(
        selection=[
            ("daily", "Day(s)"),
            ("weekly", "Week(s)"),
            ("monthly", "Month(s)"),
            ("monthlylastday", "Month(s) last day"),
            ("quarterly", "Quarter(s)"),
            ("semesterly", "Semester(s)"),
            ("yearly", "Year(s)"),
        ],
        string="Recurrence",
        required=True,
        default="monthly",
    )
    recurring_interval = fields.Integer(
        string="Invoice Every",
        required=True,
        default=1,
    )
    recurring_invoicing_type = fields.Selection(
        selection=[
            ("pre-paid", "Pre-paid"),
            ("post-paid", "Post-paid"),
        ],
        string="Invoicing Type",
        required=True,
        default="pre-paid",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        purchase_order_id = res.get("purchase_order_id") or self.env.context.get(
            "default_purchase_order_id"
        )
        if purchase_order_id:
            order = self.env["purchase.order"].browse(purchase_order_id).exists()
            if order:
                res.update(
                    {
                        "purchase_order_id": order.id,
                        "partner_id": order.partner_id.id,
                        "company_id": order.company_id.id,
                        "name": self.env._("Contract - %s") % order.name,
                        "user_id": order.user_id.id or self.env.user.id,
                    }
                )
                if "line_ids" in fields_list:
                    res["line_ids"] = self._prepare_wizard_lines(order)
        return res

    @api.model
    def _prepare_wizard_lines(self, order):
        lines = []
        for purchase_line in order.order_line.filtered(
            lambda line: not line.display_type and line.product_id
        ):
            remaining_quantity = self._get_remaining_quantity(purchase_line)
            if remaining_quantity > 0:
                lines.append(
                    (
                        0,
                        0,
                        {
                            "purchase_line_id": purchase_line.id,
                            "product_id": purchase_line.product_id.id,
                            "name": purchase_line.name,
                            "product_uom_id": purchase_line.product_uom.id,
                            "available_quantity": remaining_quantity,
                            "quantity": remaining_quantity,
                            "price_unit": purchase_line.price_unit,
                        },
                    )
                )
        return lines

    def _get_remaining_quantity(self, purchase_line):
        contract_lines = (
            self.env["contract.line"]
            .with_context(active_test=False)
            .search(
                [
                    ("purchase_line_id", "=", purchase_line.id),
                    ("is_canceled", "=", False),
                ]
            )
        )
        used_quantity = sum(
            contract_line.uom_id._compute_quantity(
                contract_line.quantity,
                purchase_line.product_uom,
            )
            for contract_line in contract_lines
        )
        return purchase_line.product_qty - used_quantity

    def action_generate_contract(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(self.env._("You must select at least one line."))
        if self.recurring_interval <= 0:
            raise ValidationError(
                self.env._("The recurring interval must be greater than zero.")
            )
        order = self.purchase_order_id
        purchase_line_ids = set()
        for line in self.line_ids:
            purchase_line = line.purchase_line_id
            if purchase_line.order_id != order:
                raise ValidationError(
                    self.env._(
                        "The selected purchase order line does not belong "
                        "to the purchase order."
                    )
                )
            if purchase_line.id in purchase_line_ids:
                raise ValidationError(
                    self.env._(
                        "The same purchase order line cannot be selected "
                        "more than once."
                    )
                )
            purchase_line_ids.add(purchase_line.id)
            remaining_quantity = self._get_remaining_quantity(purchase_line)
            if line.quantity <= 0 or line.quantity > remaining_quantity:
                raise ValidationError(
                    self.env._(
                        "The quantity for product '%s' exceeds the "
                        "available quantity or is not valid."
                    )
                    % line.product_id.display_name
                )
        contract = self.env["contract.contract"].create(
            {
                "name": self.name,
                "partner_id": order.partner_id.id,
                "company_id": order.company_id.id,
                "contract_type": "purchase",
                "purchase_order_id": order.id,
                "user_id": self.user_id.id,
                "date_start": self.date_start,
                "currency_id": order.currency_id.id,
                "line_recurrence": False,
                "recurring_rule_type": self.recurring_rule_type,
                "recurring_interval": self.recurring_interval,
                "recurring_invoicing_type": self.recurring_invoicing_type,
            }
        )
        for line in self.line_ids:
            self.env["contract.line"].create(
                {
                    "contract_id": contract.id,
                    "purchase_line_id": line.purchase_line_id.id,
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "quantity": line.quantity,
                    "uom_id": line.product_uom_id.id,
                    "specific_price": line.price_unit,
                    "automatic_price": False,
                    "date_start": self.date_start,
                }
            )
        return {
            "name": self.env._("Purchase Contract"),
            "type": "ir.actions.act_window",
            "res_model": "contract.contract",
            "res_id": contract.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_contract_type": "purchase",
            },
        }
