# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    contract_ids = fields.One2many(
        comodel_name="contract.contract",
        inverse_name="purchase_order_id",
        string="Contracts",
    )
    contract_count = fields.Integer(
        compute="_compute_contract_count",
    )

    @api.depends("contract_ids")
    def _compute_contract_count(self):
        for order in self:
            order.contract_count = len(order.contract_ids)

    def action_generate_agreement(self):
        self.ensure_one()
        available_lines = self.order_line.filtered(
            lambda line: (
                not line.display_type
                and line.product_id
                and self.env["contract.purchase.wizard"]._get_remaining_quantity(line)
                > 0
            )
        )
        if not available_lines:
            raise UserError(
                self.env._(
                    "There are no remaining quantities available "
                    "to generate a new contract."
                )
            )
        return {
            "name": self.env._("Generate Agreement"),
            "type": "ir.actions.act_window",
            "res_model": "contract.purchase.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
            },
        }

    def action_view_contracts(self):
        self.ensure_one()
        action = {
            "name": self.env._("Contracts"),
            "type": "ir.actions.act_window",
            "res_model": "contract.contract",
            "view_mode": "list,form",
            "domain": [("purchase_order_id", "=", self.id)],
            "context": {
                "default_contract_type": "purchase",
                "default_purchase_order_id": self.id,
            },
        }
        if len(self.contract_ids) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.contract_ids.id,
                }
            )
        return action
