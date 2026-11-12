# Copyright 2026 Ángel Rivas <angel.rivas@sygel.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Purchase Contract",
    "summary": "Generate supplier contracts from purchase orders",
    "version": "18.0.1.0.0",
    "category": "contract",
    "author": "Sygel",
    "website": "https://github.com/sygel-technology/sy-contract",
    "depends": [
        "purchase",
        "contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/contract_purchase_wizard_views.xml",
        "views/purchase_order_views.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
}
