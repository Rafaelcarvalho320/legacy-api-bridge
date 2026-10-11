"""Build the legacy tables and fill them with the sample data.

    python manage.py load_legacy

Exists so the project can be tried in one command. In a real deployment the
tables are already there and this is the one thing you would never run.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from legacy import schema
from legacy.models import Client, Order, OrderItem


class Command(BaseCommand):
    help = "Create the legacy tables from SQL and load the sample rows."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--no-seed",
            action="store_true",
            help="Create the tables but leave them empty.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        schema.reset(seed=not options["no_seed"])
        self.stdout.write(self.style.SUCCESS("legacy schema created"))
        if options["no_seed"]:
            return
        self.stdout.write(
            f"  clients visible: {Client.objects.count()} "
            f"(of {Client.all_objects.count()} rows in TB_CLI)"
        )
        self.stdout.write(
            f"  orders visible:  {Order.objects.count()} "
            f"(of {Order.all_objects.count()} rows in TB_PED)"
        )
        self.stdout.write(f"  order lines:     {OrderItem.objects.count()}")
