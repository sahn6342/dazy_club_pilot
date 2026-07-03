"""
POS orchestration service — thin layer over repositories.
Keeps route handlers free of multi-repo coordination logic.
"""
from typing import Optional

from db_models import OrderRow, KotRow, OrderItemRow


def create_order(
    order_type: str,
    created_by: str,
    items: list,  # list of OrderItemCreate
    table_id: Optional[str],
    notes: Optional[str],
    booking_id: Optional[str] = None,
) -> OrderRow:
    """
    Create an order and add all requested items in one go.
    Fetches menu item details (price, tax, name, hsn) from the DB.
    """
    from deps import order_repo, menu_item_repo

    order = order_repo.create(
        order_type=order_type,
        created_by=created_by,
        table_id=table_id,
        notes=notes,
        booking_id=booking_id,
    )
    for item_req in items:
        menu_item = menu_item_repo.get_by_id(item_req.menu_item_id)
        if menu_item is None:
            continue  # silently skip unknown items; route layer validates existence
        order_repo.add_item(
            order_id=order.id,
            menu_item_id=menu_item.id,
            qty=item_req.qty,
            unit_price=float(menu_item.price),
            tax_rate=float(menu_item.taxRatePercent),
            name_snapshot=menu_item.name,
            hsn_sac=menu_item.hsnSac,
        )
    # Re-fetch to get updated totals
    refreshed = order_repo.get_by_id(order.id)
    return refreshed or order


def fire_kot(order_id: str, cashier: dict) -> list[KotRow]:
    """
    Group all pending (non-voided, no KOT yet) order items by station.
    Create one KOT per station group.
    Returns list of created KotRow objects.
    """
    from deps import order_repo, kot_repo

    items: list[OrderItemRow] = order_repo.get_items(order_id)
    # Only items that are active and have not yet been sent to a KOT
    pending = [i for i in items if not i.voided and i.kot_id is None]

    # Group by station — need to fetch menu item station from item snapshot or fallback
    # We group by the item's existing kotStatus=None items; station comes from menu_item
    from db import _session
    from db_models import MenuItemRow
    from sqlalchemy import select

    station_groups: dict[str, list[str]] = {}
    with _session() as s:
        for item in pending:
            menu_item = s.get(MenuItemRow, item.menu_item_id)
            station = menu_item.station if menu_item else "kitchen"
            station_groups.setdefault(station, []).append(item.id)

    kots = []
    for station, item_ids in station_groups.items():
        kot = kot_repo.create(order_id=order_id, station=station, item_ids=item_ids)
        kots.append(kot)
    return kots
