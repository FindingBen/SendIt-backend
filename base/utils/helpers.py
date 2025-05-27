

def map_products_n_orders(products=None, orders=None):

    product_list = products.get("data", {}).get(
        "products", {}).get("edges", {})

    orders_list = orders.get("data", {}).get("orders", {}).get("edges", {})

    mapped_orders = []
    mapped_products = []

    for order in orders_list:
        order_node = order.get("node", {})
        order_id = order_node.get("id")
        order_name = order_node.get("name")
        created_at = order_node.get("createdAt")
        total_price = order_node.get("totalPriceSet", {}).get(
            "shopMoney", {}).get("amount")
        customer = order_node.get("customer")
        line_items = order_node.get("lineItems", {}).get("edges", [])

        # Aggregate by product_id within this order
        product_map = {}
        for item in line_items:
            item_node = item.get("node", {})
            product_id = item_node.get("product", {}).get("id")
            product_title = item_node.get("product", {}).get("title")
            variant_id = item_node.get("product", {}).get("id")
            variant_title = item_node.get("title")
            quantity = item_node.get("quantity")
            restockable = item_node.get("restockable")

            if product_id not in product_map:
                product_map[product_id] = {
                    "product_id": product_id,
                    "product_title": product_title,
                    "total_quantity": 0,
                    "variants": [],
                }
            product_map[product_id]["total_quantity"] += quantity
            product_map[product_id]["variants"].append({
                "variant_id": variant_id,
                "variant_title": variant_title,
                "quantity": quantity,
                "restockable": restockable,
            })

        # For each product in this order, create an order_object
        for product in product_map.values():
            order_object = {
                "order_id": order_id,
                "order_name": order_name,
                "created_at": created_at,
                "total_price": total_price,
                "customer": customer,
                "product_id": product["product_id"],
                "product_title": product["product_title"],
                "total_orders": product["total_quantity"],
                "variants": product["variants"],
            }
            mapped_orders.append(order_object)

    for product in product_list:
        node = product.get("node", {})
        images = node.get("images", {}).get("edges", [])
        print(images)
        print('SSS')
        image_url = images[0]["node"]["src"] if images else None
        mapped_product = {
            "id": node.get("id"),
            "title": node.get("title"),
            "createdAt": node.get("createdAt"),
            "hasOutOfStockVariants": node.get("hasOutOfStockVariants"),
            "publishedAt": node.get("publishedAt"),
            "tags": node.get("tags"),
            "totalInventory": node.get("totalInventory"),
            "variantsCount": node.get("variantsCount", {}).get("count"),
            "image": image_url,
        }
        mapped_products.append(mapped_product)

    product_orders_map = {}
    for order in mapped_orders:
        pid = order["product_id"]
        if pid not in product_orders_map:
            product_orders_map[pid] = []
        product_orders_map[pid].append(order)

    # Merge product info with order info
    final_products = []
    for product in mapped_products:
        pid = product["id"]
        related_orders = product_orders_map.get(pid, [])
        # Aggregate total_orders and variants if needed
        total_orders = sum(o["total_orders"] for o in related_orders)
        all_variants = []
        for o in related_orders:
            all_variants.extend(o["variants"])
        # Remove duplicates in variants if needed (optional)
        product_with_orders = {
            **product,
            "total_orders": total_orders,
            "orders": related_orders,
            "variants_purchased": all_variants,
        }
        final_products.append(product_with_orders)

    return final_products


def map_single_product_with_orders(product=None, orders=None):
    if not product:
        return {}
    node = product.get("node", {})
    product_id = product['id']
    print(product)
    # Prepare product fields
    images = product['images'].get("edges", [])
    # image_url = images[0]["node"]["src"] if images else None
    print(images)
    mapped_product = {
        "id": product['id'],
        "title": product['title'],
        "createdAt": product['createdAt'],
        "hasOutOfStockVariants": product['hasOutOfStockVariants'],
        "publishedAt": product['publishedAt'],
        "tags": product['tags'],
        "images": images,
        "totalInventory": product['totalInventory'],
        "variantsCount": product.get('variantsCount', {})['count'],
        "single_image": images[0] if images else None,
    }
    # Aggregate order info for this product
    orders_list = orders.get("data", {}).get("orders", {}).get("edges", [])
    related_orders = []
    total_orders = 0
    all_variants = []

    for order in orders_list:

        order_node = order.get("node", {})
        order_id = order_node.get("id")
        order_name = order_node.get("name")
        created_at = order_node.get("createdAt")
        total_price = order_node.get("totalPriceSet", {}).get(
            "shopMoney", {}).get("amount")
        customer = order_node.get("customer")
        line_items = order_node.get("lineItems", {}).get("edges", [])

        # Check if this order contains the product
        product_found = False
        order_variants = []
        order_total_quantity = 0

        for item in line_items:
            item_node = item.get("node", {})
            item_product_id = item_node.get("product", {}).get("id")

            if item_product_id == product_id:
                product_found = True
                variant_id = item_node.get("product")['id']
                variant_title = item_node.get("product")['title']
                quantity = item_node.get("quantity")
                restockable = item_node.get("restockable")
                order_total_quantity += quantity
                order_variants.append({
                    "variant_id": variant_id,
                    "variant_title": variant_title,
                    "quantity": quantity,
                    "restockable": restockable,
                })

        if product_found:
            total_orders += order_total_quantity
            all_variants.extend(order_variants)
            related_orders.append({
                "order_id": order_id,
                "order_name": order_name,
                "created_at": created_at,
                "total_price": total_price,
                "customer": customer,
                # "total_orders": order_total_quantity,
                "variants": order_variants,
            })

    # Attach order info to product
    mapped_product["total_orders"] = total_orders
    mapped_product["orders"] = related_orders
    mapped_product["variants_purchased"] = all_variants

    # If no orders, set fields to None or 0 as needed
    if not related_orders:
        mapped_product["total_orders"] = 0
        mapped_product["orders"] = []
        mapped_product["variants_purchased"] = []
    return mapped_product
