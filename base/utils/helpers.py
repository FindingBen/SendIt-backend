from datetime import datetime, timezone
from base.models import ShopifyStore


class Utils:
    def __init__(self, shopify_domain=None):
        self._shopify_domain = shopify_domain

    def map_products_n_orders(self, products=None, orders=None):

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

    def map_single_product_with_orders(self, product=None, orders=None):
        if not product:
            return {}
        node = product.get("node", {})
        product_id = product['id']

        # Prepare product fields
        images = product['images'].get("edges", [])
        # image_url = images[0]["node"]["src"] if images else None

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

    def get_insights(self, product):

        TIME_SCORE = 0
        STOCK_SCORE = 0
        TAGS_SCORE = 0
        VARIANTS_SCORE = 0
        SALES_SCORE = 0
        insights = []
        if "shopify_product" in product:
            product = product["shopify_product"]
        created_at = product.get('createdAt', None)

        if created_at:
            created_dt = datetime.strptime(
                created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            days_on_store = (datetime.now(timezone.utc) - created_dt).days
            if days_on_store > 180:
                insights.append(
                    f"This product has been in your store for over {days_on_store//30} months. Consider a promotion or content refresh.")
            elif days_on_store > 30:
                insights.append(
                    f"This product has been in your store for {days_on_store} days.")

        total_inventory = product.get('totalInventory', 0)

        if total_inventory == 0:
            insights.append(
                "This product is currently out of stock. Restocking could boost sales.")
        elif total_inventory < 5:
            insights.append(
                "Inventory is running low. Consider restocking soon.")

        # 3. Out of Stock Variants
        if product.get('hasOutOfStockVariants', 0):
            insights.append(
                "Some variants are out of stock. Promote available variants or restock popular ones.")

        variants_count = product.get('variantsCount', 0)
        variants_purchased = product.get('variants_purchased', [])

        unique_variants_purchased = set(v["variant_id"]
                                        for v in variants_purchased)
        if variants_count > 1:
            if len(unique_variants_purchased) == variants_count:
                insights.append(
                    "All variants of this product have been purchased. Highlight its versatility in your marketing!")
            elif len(unique_variants_purchased) == 1:
                insights.append(
                    "Only one variant has been purchased. Consider promoting other variants to diversify sales.")
            else:
                insights.append(
                    f"{len(unique_variants_purchased)} out of {variants_count} variants have sales. Promote the less popular variants.")

        total_orders = product.get('total_orders', 0)
        if total_orders == 0:
            insights.append(
                "This product hasn't been ordered yet. Try featuring it in a campaign or bundle.")
        elif total_orders < 5:
            insights.append(
                "This product has a few sales. Consider a special offer to boost interest.")
        else:
            insights.append(
                f"This product has {total_orders} orders. Highlight its popularity in your content!")

        # 6. Tags
        tags = product.get('tags', [])
        if not tags:
            insights.append(
                "This product has no tags. Adding relevant tags can improve discoverability.")
        else:
            insights.append(
                f"Tags: {', '.join(tags)}. Use these in your content and ads.")

        if product.get("isGiftCard"):
            insights.append(
                "This product is a gift card. Promote it during holidays or special occasions.")

        if not product.get("images"):
            insights.append(
                "This product has no images. Adding high-quality images can increase conversions.")

        return insights

    def get_package_limits(self, user_package):
        package_limits = {
            'Gold package': {'contact_lists': 20, 'recipients': "Unlimited"},
            'Silver package': {'contact_lists': 10, 'recipients': 10000},
            'Basic package': {'contact_lists': 3, 'recipients': 5000},
            'Trial Plan': {'contact_lists': 1, 'recipients': 100}
        }
        if user_package.plan_type in package_limits:
            limits = package_limits[user_package.plan_type]
        else:
            limits = package_limits['Trial Plan']
        return limits

    def get_shopify_token(self, user):

        shopify_object = ShopifyStore.objects.get(email=user.email)
        return shopify_object

    def convert_keys(self, profile):
        print('Converting keys:', profile)
        return {
            "firstName": profile.get("first_name"),
            "lastName": profile.get("last_name"),
            "phone": profile.get("phone"),
            "email": profile.get("email"),
        }

    def flag_recipients(self, user, recipients_queryset):
        """
        Flags recipients as allowed or not based on the user's current package.
        Returns metadata if recipients were flagged due to a downgrade.
        """
        user_package = user.serialize_package_plan()
        recipients_limit = user_package.get('recipients_limit')

        if not recipients_limit:
            print(f"Invalid package limit for user {user.email}")
            return "NO RECIPIENTS"

        if recipients_limit == "Unlimited":
            # Only act if any recipients were previously disallowed
            if recipients_queryset.filter(allowed=False).exists():
                recipients_queryset.update(allowed=True)
                return {
                    "flagged_count": 0,
                    "flagged_ids": [],
                    "was_downgraded": False,
                    "message": "All recipients allowed due to Unlimited plan."
                }
            return "UNLIMITED"

        try:
            limit = int(recipients_limit)
        except ValueError:
            print(
                f"Malformed limit value for user {user.email}: {recipients_limit}")
            return "ERRRROORRR"

        # Sort by created_at, keep oldest recipients (or reverse for newest)
        recipients = recipients_queryset.order_by('created_at')
        allowed_ids = list(recipients[:limit].values_list('id', flat=True))
        disallowed_qs = recipients[limit:]
        disallowed_ids = list(disallowed_qs.values_list('id', flat=True))

        if not disallowed_ids:
            return "NO DISSALOWED"  # No downgrade effect, nothing to flag

        from base.models import Contact
        Contact.objects.filter(id__in=allowed_ids).update(allowed=True)
        Contact.objects.filter(id__in=disallowed_ids).update(allowed=False)

        print(
            f"Flagged {len(disallowed_ids)} recipients for user {user.email} due to downgrade")

        return {
            "flagged_count": len(disallowed_ids),
            "flagged_ids": disallowed_ids,
            "was_downgraded": True,
            "message": f"{len(disallowed_ids)} recipients disabled due to new plan limit of {limit}"
        }
