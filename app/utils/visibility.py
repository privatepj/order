"""按角色隐藏敏感字段（读取侧）。"""
from types import SimpleNamespace

from flask_login import current_user


def is_admin():
    if not current_user.is_authenticated:
        return False
    return getattr(current_user, "role_code", None) == "admin"


def customer_view(customer):
    """供模板使用：非管理员隐藏联系人、电话、税点。"""
    if customer is None:
        return SimpleNamespace(
            id=None,
            customer_code="",
            short_code=None,
            name="",
            contact=None,
            phone=None,
            address=None,
            payment_terms=None,
            remark=None,
            company_id=None,
            company=None,
            tax_point=None,
            fax=None,
        )
    admin = is_admin()
    tax = customer.tax_point
    tax_display = float(tax) if tax is not None else None
    return SimpleNamespace(
        id=customer.id,
        customer_code=customer.customer_code,
        short_code=getattr(customer, "short_code", None),
        name=customer.name,
        contact=customer.contact if admin else None,
        phone=customer.phone if admin else None,
        fax=customer.fax if admin else None,
        address=customer.address,
        payment_terms=customer.payment_terms,
        remark=customer.remark,
        company_id=customer.company_id,
        company=customer.company,
        tax_point=tax_display if admin else None,
    )


def customer_product_view(cp):
    """非管理员隐藏单价、币种。"""
    if cp is None:
        return None
    admin = is_admin()
    price = cp.price
    mat = (cp.product.product_code or "") if cp.product else ""
    return SimpleNamespace(
        id=cp.id,
        customer_id=cp.customer_id,
        product_id=cp.product_id,
        customer_material_no=cp.customer_material_no,
        material_no=mat,
        unit=cp.unit,
        price=float(price) if admin and price is not None else None,
        currency=cp.currency if admin else None,
        remark=cp.remark,
        customer=customer_view(cp.customer) if cp.customer else None,
        product=cp.product,
    )


def order_item_view(item):
    """非管理员隐藏单价、金额。"""
    if item is None:
        return None
    admin = is_admin()
    pr, amt = item.price, item.amount
    mat = ""
    if item.customer_product and item.customer_product.product:
        mat = item.customer_product.product.product_code or ""
    return SimpleNamespace(
        id=item.id,
        order_id=item.order_id,
        customer_product_id=item.customer_product_id,
        product_name=item.product_name,
        product_spec=item.product_spec,
        customer_material_no=item.customer_material_no,
        material_no=mat or "",
        quantity=item.quantity,
        unit=item.unit,
        price=float(pr) if admin and pr is not None else None,
        amount=float(amt) if admin and amt is not None else None,
        show_pricing=admin,
    )
