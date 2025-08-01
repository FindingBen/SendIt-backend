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
    CREATE_CUSTOMER_QUERY,
    GET_ALL_PRODUCTS,
    DELETE_CUSTOMER_QUERY,
    UPDATE_CUSTOMER_QUERY,
    GET_SHOP_ORDERS,
    GET_SHOP_INFO
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
                break  # Fail fast if Shopify API error

            data = response.json()

            # Extract data safely
            try:
                edges = data['data']['customers']['edges']
                page_info = data['data']['customers']['pageInfo']
            except (KeyError, TypeError):
                break  # Shopify response is malformed

            all_customers.extend(edges)
            total_fetched += len(edges)

            if not page_info.get('hasNextPage') or not edges:
                break  # No more pages

            cursor = edges[-1]['cursor']

        return all_customers

    def create_customers(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        customer_data = {
            "firstName": self._request.data.get("firstName"),
            "lastName": self._request.data.get("lastName"),
            "email": self._request.data.get("email"),
            "phone": self._request.data.get("phone"),
        }

        # GraphQL variables
        variables = {
            "input": customer_data
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
                "email": customer.get("email"),
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

            if errors:
                results.append({"success": False, "error": errors})
            else:
                results.append({"success": True})

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

    def delete_customer(self):
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        shopify_id = self._request.data.get(
            'id')  # Safely get the value of 'id'

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

    # def get_products(self):
    #     headers = {
    #         "X-Shopify-Access-Token": self._token,
    #         "Content-Type": "application/json",
    #     }

    #     variables = {
    #         "first": 10,
    #     }

    #     response = requests.post(
    #         self._url,
    #         headers=headers,
    #         json={"query": self._query, "variables": variables},
    #     )

    #     return response

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
            "first": 10
        }

        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": body_request},
        )
        # Return the response from Shopify's API
        return response

    def get_products(self, variable):
        return self.run_query(GET_ALL_PRODUCTS, variable)

    def get_shop_orders(self, variable=None):
        return self.run_query(GET_SHOP_ORDERS, variable)

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
