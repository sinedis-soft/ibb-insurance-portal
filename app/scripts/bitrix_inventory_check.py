from __future__ import annotations

import asyncio
import sys

from app.integrations.bitrix import get_bitrix24_client
from app.integrations.bitrix.field_mapping import BITRIX_DEAL_FIELDS


async def run() -> int:
    client = get_bitrix24_client()
    deal_fields, company_fields, contact_fields = await asyncio.gather(
        client.fetch_deal_fields(),
        client.fetch_company_fields(),
        client.fetch_contact_fields(),
    )
    print("Bitrix24 field inventory")
    for logical_name, field_code in BITRIX_DEAL_FIELDS.items():
        field = deal_fields.get(field_code)
        exists = field is not None
        field_type = field.get("type") if isinstance(field, dict) else None
        status = "ok" if exists else "missing"
        print(f"deal.{logical_name}\t{field_code}\texists={str(exists).lower()}\ttype={field_type}\tstatus={status}")
    print(f"company.fields\ttotal={len(company_fields)}")
    print(f"contact.fields\ttotal={len(contact_fields)}")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
