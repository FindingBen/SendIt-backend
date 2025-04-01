GET_CUSTOMERS_QUERY = """
query getCustomers($first: Int, $after: String, $query: String) {
  customers(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        firstName
        lastName
        email
        phone
        createdAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

CREATE_CUSTOMER_QUERY = """
mutation createCustomer($input: CustomerInput!) {
  customerCreate(input: $input) {
    customer {
      id
      firstName
      lastName
      email
      phone
      createdAt
    }
    userErrors {
      field
      message
    }
  }
}
"""
