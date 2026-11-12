# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestContractPurchase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "supplier_rank": 1,
            }
        )
        cls.product_1 = cls.env["product.product"].create(
            {
                "name": "Test Product 1",
                "purchase_ok": True,
                "list_price": 100.0,
                "standard_price": 80.0,
            }
        )
        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "Test Product 2",
                "purchase_ok": True,
                "list_price": 200.0,
                "standard_price": 150.0,
            }
        )
        cls.purchase_order = cls.env["purchase.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_1.id,
                            "name": "Test Product 1",
                            "product_qty": 10.0,
                            "product_uom": cls.product_1.uom_po_id.id,
                            "price_unit": 80.0,
                            "date_planned": "2026-11-11 10:00:00",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_2.id,
                            "name": "Test Product 2",
                            "product_qty": 5.0,
                            "product_uom": cls.product_2.uom_po_id.id,
                            "price_unit": 150.0,
                            "date_planned": "2026-11-11 10:00:00",
                        },
                    ),
                ],
            }
        )
        cls.purchase_line_1 = cls.purchase_order.order_line.filtered(
            lambda line: line.product_id == cls.product_1
        )
        cls.purchase_line_2 = cls.purchase_order.order_line.filtered(
            lambda line: line.product_id == cls.product_2
        )

    def test_generate_contract(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )
        self.assertEqual(len(wizard.line_ids), 2)
        wizard.action_generate_contract()
        contract = self.env["contract.contract"].search(
            [("purchase_order_id", "=", self.purchase_order.id)]
        )
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract.partner_id, self.partner)
        self.assertEqual(contract.contract_type, "purchase")
        self.assertEqual(len(contract.contract_line_ids), 2)
        for purchase_line in self.purchase_order.order_line:
            contract_line = contract.contract_line_ids.filtered(
                lambda line, purchase_line=purchase_line: (
                    line.purchase_line_id == purchase_line
                )
            )
            self.assertEqual(len(contract_line), 1)
            self.assertEqual(contract_line.product_id, purchase_line.product_id)
            self.assertEqual(contract_line.quantity, purchase_line.product_qty)
            self.assertEqual(contract_line.price_unit, purchase_line.price_unit)

    def test_generate_partial_contract(self):
        Wizard = self.env["contract.purchase.wizard"]
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        for line in wizard.line_ids:
            if line.product_id == self.product_1:
                line.quantity = 4.0
            else:
                line.quantity = 2.0
        wizard.action_generate_contract()
        second_wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        self.assertEqual(len(second_wizard.line_ids), 2)
        for line in second_wizard.line_ids:
            if line.product_id == self.product_1:
                self.assertEqual(line.available_quantity, 6.0)
                self.assertEqual(line.quantity, 6.0)
            else:
                self.assertEqual(line.available_quantity, 3.0)
                self.assertEqual(line.quantity, 3.0)

    def test_generate_contract_without_remaining_quantity(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )
        wizard.action_generate_contract()
        with self.assertRaises(UserError):
            self.purchase_order.action_generate_agreement()

    def test_canceled_contract_line_releases_quantity(self):
        Wizard = self.env["contract.purchase.wizard"]
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        wizard.action_generate_contract()
        contract_line = self.env["contract.line"].search(
            [
                ("purchase_line_id", "=", self.purchase_line_1.id),
                ("is_canceled", "=", False),
            ],
            limit=1,
        )
        self.assertTrue(contract_line)
        contract_line.write({"is_canceled": True})
        second_wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        self.assertEqual(len(second_wizard.line_ids), 1)
        line = second_wizard.line_ids[0]
        self.assertEqual(line.product_id, self.product_1)
        self.assertEqual(line.available_quantity, 10.0)
        self.assertEqual(line.quantity, 10.0)

    def test_contract_line_exceeds_purchase_quantity(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )
        wizard.action_generate_contract()
        contract_line = self.env["contract.line"].search(
            [("purchase_line_id", "=", self.purchase_line_1.id)],
            limit=1,
        )
        self.assertTrue(contract_line)
        with self.assertRaises(ValidationError):
            contract_line.write({"quantity": 11.0})
        self.assertEqual(contract_line.quantity, 10.0)

    def test_purchase_line_quantity_below_contracted_quantity(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )
        wizard.action_generate_contract()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.purchase_line_1.write({"product_qty": 9.0})
        self.assertEqual(self.purchase_line_1.product_qty, 10.0)

    def test_archived_contract_keeps_committed_quantity(self):
        Wizard = self.env["contract.purchase.wizard"]
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        for line in wizard.line_ids:
            if line.product_id == self.product_1:
                line.quantity = 4.0
            else:
                line.quantity = 2.0
        wizard.action_generate_contract()
        contract = self.env["contract.contract"].search(
            [("purchase_order_id", "=", self.purchase_order.id)],
            limit=1,
        )
        self.assertTrue(contract)
        contract.write({"active": False})
        self.assertFalse(contract.active)
        second_wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        self.assertEqual(len(second_wizard.line_ids), 2)
        for line in second_wizard.line_ids:
            if line.product_id == self.product_1:
                self.assertEqual(line.available_quantity, 6.0)
                self.assertEqual(line.quantity, 6.0)
            else:
                self.assertEqual(line.available_quantity, 3.0)
                self.assertEqual(line.quantity, 3.0)

    def test_deleted_contract_line_releases_quantity(self):
        Wizard = self.env["contract.purchase.wizard"]
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        wizard.action_generate_contract()
        contract_line = self.env["contract.line"].search(
            [("purchase_line_id", "=", self.purchase_line_1.id)],
            limit=1,
        )
        self.assertTrue(contract_line)
        contract_line.unlink()
        second_wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        self.assertEqual(len(second_wizard.line_ids), 1)
        line = second_wizard.line_ids[0]
        self.assertEqual(line.purchase_line_id, self.purchase_line_1)
        self.assertEqual(line.available_quantity, 10.0)
        self.assertEqual(line.quantity, 10.0)

    def test_generate_contract_with_modified_lines(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )
        wizard_line = wizard.line_ids.filtered(
            lambda line: line.product_id == self.product_1
        )
        wizard_line.write(
            {
                "quantity": 4.0,
                "name": "Custom contract description",
                "price_unit": 95.0,
            }
        )
        wizard.line_ids.filtered(
            lambda line: line.product_id == self.product_2
        ).unlink()
        wizard.action_generate_contract()
        contract = self.env["contract.contract"].search(
            [("purchase_order_id", "=", self.purchase_order.id)],
            limit=1,
        )
        self.assertEqual(len(contract.contract_line_ids), 1)
        contract_line = contract.contract_line_ids[0]
        self.assertEqual(contract_line.purchase_line_id, self.purchase_line_1)
        self.assertEqual(contract_line.quantity, 4.0)
        self.assertEqual(contract_line.name, "Custom contract description")
        self.assertEqual(contract_line.price_unit, 95.0)

    def test_generate_contract_configuration(self):
        wizard = (
            self.env["contract.purchase.wizard"]
            .with_context(
                default_purchase_order_id=self.purchase_order.id,
            )
            .create({})
        )

        wizard.write(
            {
                "name": "Test Purchase Agreement",
                "date_start": "2026-12-01",
                "user_id": self.env.user.id,
                "recurring_rule_type": "yearly",
                "recurring_interval": 2,
                "recurring_invoicing_type": "post-paid",
            }
        )

        wizard.action_generate_contract()

        contract = self.env["contract.contract"].search(
            [("purchase_order_id", "=", self.purchase_order.id)],
            limit=1,
        )

        self.assertTrue(contract)
        self.assertEqual(contract.name, "Test Purchase Agreement")
        self.assertEqual(contract.date_start, fields.Date.to_date("2026-12-01"))
        self.assertEqual(contract.user_id, self.env.user)
        self.assertEqual(contract.recurring_rule_type, "yearly")
        self.assertEqual(contract.recurring_interval, 2)
        self.assertEqual(contract.recurring_invoicing_type, "post-paid")

    def test_generate_contract_invalid_values(self):
        Wizard = self.env["contract.purchase.wizard"]
        invalid_quantities = [0.0, -1.0, 11.0]
        for quantity in invalid_quantities:
            with self.subTest(quantity=quantity):
                wizard = Wizard.with_context(
                    default_purchase_order_id=self.purchase_order.id,
                ).create({})
                wizard_line = wizard.line_ids.filtered(
                    lambda line: line.product_id == self.product_1
                )
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    wizard_line.write({"quantity": quantity})
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        wizard.line_ids.unlink()
        with self.assertRaises(UserError), self.cr.savepoint():
            wizard.action_generate_contract()
        wizard = Wizard.with_context(
            default_purchase_order_id=self.purchase_order.id,
        ).create({})
        wizard.recurring_interval = 0
        with self.assertRaises(ValidationError), self.cr.savepoint():
            wizard.action_generate_contract()
