import requests
from rest_framework import status
from rest_framework.response import Response
from .models import CustomUser
import phonenumbers
from .queries import (
    GET_CUSTOMERS_QUERY,
    GET_TOTAL_CUSTOMERS_NR,
    GET_CUSTOMERS_ORDERS,
    GET_PRODUCT,
    UPDATE_PRODUCT_VARIANTS_BULK,
    CREATE_CUSTOMER_QUERY,
    GET_ALL_PRODUCTS,
    DELETE_CUSTOMER_QUERY,
    UPDATE_CUSTOMER_QUERY,
    GET_SHOP_ORDERS,
    UPDATE_IMAGE,
    UPDATE_PRODUCT_WITH_SEO,
    GET_SHOP_INFO_2
)


class ShopifyFactoryFunction:
    def __init__(self,  domain, token, url, request=None, query=None, headers=None):
        self._query = query
        self._domain = domain
        self._token = token
        self._url = url
        self._request = request
        self._headers = headers

    def run_query(self, query, variables=None):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": query, "variables": variables or {}},
        )
        return response

    def get_total_customers(self):
        url = f"https://{self._domain}/admin/api/2025-01/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json={
                                 "query": self._query})
        if response.status_code == 200:
            data = response.json()
            print('HEREEE', data)
            total_count = data.get("data", {}).get(
                "customersCount", {}).get("count", 0)
            return total_count
        else:
            raise Exception(f"Failed to fetch customers: {response.json()}")

    def get_customers(self):
        search_query = self._request.GET.get('search', '')
        sort_by = self._request.GET.get('sort_by', None)
        reverse = self._request.GET.get('reverse', 'false').lower() == 'true'
        user = CustomUser.objects.get(id=self._request.user.id)
        user_package = user.serialize_package_plan()
        recipients_limit = user_package['recipients_limit']
        shopify_limit = 250

        headers = {
            "X-Shopify-Access-Token": self._token,
        }

        all_customers = []
        cursor = None
        total_fetched = 0

        unlimited = recipients_limit == "Unlimited"
        limit = float('inf') if unlimited else int(recipients_limit)

        while total_fetched < limit:
            variables = {
                "first": min(shopify_limit, limit - total_fetched),
                "after": cursor,
                "query": search_query,
                "reverse": reverse,
            }

            response = requests.post(
                self._url,
                headers=headers,
                json={"query": self._query, "variables": variables},
            )

            if response.status_code != 200:
                raise Exception(f"Shopify API error: {response.text}")

            data = response.json()
            # Extract safely
            try:
                edges = data['data']['customers']['edges']
                #edges.sort(key=lambda c: self.get_marketing_state(c) != "SUBSCRIBED")
                page_info = data['data']['customers']['pageInfo']

            except (KeyError, TypeError):
                raise Exception("Invalid Shopify API response format")
            
            all_customers.extend(edges)
            total_fetched += len(edges)
            if not page_info.get('hasNextPage') or not edges:
                break  # No more pages
            #
            # 🚨 Check if limit reached mid-loop
            if not unlimited and total_fetched >= limit:
                break
            
        return all_customers

    def get_marketing_state(self,customer):
        """Safely extract the marketingState value."""
        try:
            node = customer.get("node") or {}
            default_phone = node.get("defaultPhoneNumber") or {}
            return default_phone.get("marketingState", "NONE")
        except Exception:
            return "NONE"

    def create_customers(self, source='standard'):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        sms_opt_in = self._request.data.get("sms_opt_in", "NOT_SUBSCRIBED")
        sms_opt_in = sms_opt_in.upper() if sms_opt_in else "NOT_SUBSCRIBED"
        if sms_opt_in not in ["SUBSCRIBED", "NOT_SUBSCRIBED", "PENDING"]:
            sms_opt_in = "NOT_SUBSCRIBED"
        customer_data = {
            "firstName": self._request.data.get("firstName"),
            "lastName": self._request.data.get("lastName"),
            "email": self._request.data.get("email"),
            "phone": self._request.data.get("phone"),
            "smsMarketingConsent": {
                    "marketingState": sms_opt_in,
                    "marketingOptInLevel": "SINGLE_OPT_IN"
                }
        }
        
        variables = {
            "input": {
                **customer_data
            }
        }


        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )

        return response

    def create_customers_bulk(self):
        results = []
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        bulk_customers = self._request.data.get('data', None).get('bulk_data')

        for customer in bulk_customers:

            customer_data = {
                "firstName": customer.get("firstName"),
                "lastName": customer.get("lastName"),
                # "email": customer.get("email"),
                "phone": f'+{customer.get("phone")}',
            }

            variables = {
                "input": customer_data
            }

            response = requests.post(
                self._url,
                headers=headers,
                json={"query": self._query, "variables": variables},
            )
            data = response.json()
            errors = data.get("errors") or data.get("data", {}).get(
                "customerCreate", {}).get("userErrors", [])

            customer_info = data.get("data", {}).get(
                "customerCreate", {}).get("customer")

            if errors or not customer_info:
                results.append({"success": False, "error": errors})
            else:
                results.append({"success": True, "customer": customer_info})

        return results

    def update_customer(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        shopify_id = self._request.data.get('id')

        customer_data = {
            "id": shopify_id,
            "firstName": self._request.data.get("firstName"),
            "lastName": self._request.data.get("lastName"),
            "email": self._request.data.get("email"),
            "phone": self._request.data.get("phone"),
        }
        phone = customer_data.get("phone")

        customer_data['phone'] = f'+{phone}'
        customer_data = {key: value for key,
                         value in customer_data.items() if value is not None}

        print(customer_data)
        variables = {

            "input": customer_data
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )
        data = response.json()
        return data

    def get_shop_info(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query},
        )

        return response

    def get_single_product(self):
        url = f"https://{self._domain}/admin/api/2025-01/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        variables = {
            "first": 10,
            "id": ""
        }

        response = requests.post(
            url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )

        return response

    def get_products_insights(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        shopify_id = self._request.data.get('id')

        body_request = {
            "id": shopify_id,
            "first": 50
        }

        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": body_request},
        )
        # Return the response from Shopify's API
        return response

    def get_business_info(self):
        return self.run_query(GET_SHOP_INFO_2)

    def get_product(self, product):
        variables = {
            "id": product.id}
        return self.run_query(GET_PRODUCT, variables)
    
    def get_product_for_opt(self, product):
        variables = {
            "id": product.get('product_id')}
        response = self.run_query(GET_PRODUCT, variables)
        
        data = response.json()
        print(data)
        data = data.get("data", {}).get("product", {})
        images_edges = (data.get("images") or {}).get("edges", []) or []
        images = []
        for edge in images_edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if not node:
                continue
            images.append({
                "id": node.get("id"),
                "src": node.get("src"),
                "altText": node.get("altText") or ""
            })
            # convenience: just the URL list
        # images = [img["src"] for img in images if img.get("src")]
        return data, images

    def get_products(self, variable):
        return self.run_query(GET_ALL_PRODUCTS, variable)

    def update_product_variants(self, variable):
        return self.run_query(UPDATE_PRODUCT_VARIANTS_BULK, variable)

    def get_shop_orders(self, variable=None):
        return self.run_query(GET_SHOP_ORDERS, variable)

    def delete_customer(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        shopify_id = self._request.data.get('id')
        print(shopify_id)
        variables = {

            "id": shopify_id
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )
        data = response.json()
        return data

    def create_reccuring_charge(self, variable):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variable},
        )
        return response

    def get_users_charge(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query},
        )

        return response

    def get_users_billings(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query},
        )

        return response
    
    def product_update(self, variable):
        
        return self.run_query(UPDATE_PRODUCT_WITH_SEO,variable)

    def product_image_update(self, variable):
        return self.run_query(UPDATE_IMAGE, variable)

    def cancel_recurring_charge(self, variable):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variable},
        )
        return response
