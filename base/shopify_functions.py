import requests
from rest_framework import status
from rest_framework.response import Response
from .models import CustomUser


class ShopifyFactoryFunction:
    def __init__(self, query, domain, token, url, request=None):
        self._query = query
        self._domain = domain
        self._token = token
        self._url = url
        self._request = request

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
        headers = {
            "X-Shopify-Access-Token": self._token,
        }

        variables = {
            # Number of customers to fetch per request
            "first": user_package['recipients_limit'],
            "after": None,  # Cursor for pagination
            "query": search_query,  # Optional search query
            "sortKey": sort_by.upper(),  # Sort key (e.g., CREATED_AT, FIRST_NAME)
            "reverse": reverse,  # Reverse the order if true
        }

        response = requests.post(
            self._url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )
        # Return the response from Shopify's API
        return response

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
        customer_data = {key: value for key,
                         value in customer_data.items() if value is not None}
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

    def get_products(self):
        url = f"https://{self._domain}/admin/api/2025-01/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }

        variables = {
            "first": 5,

        }

        response = requests.post(
            url,
            headers=headers,
            json={"query": self._query, "variables": variables},
        )

        return response
