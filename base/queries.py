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


DELETE_CUSTOMER_QUERY = """
mutation customerDelete($id: ID!) {
  customerDelete(input: {id: $id}) {
    deletedCustomerId
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_CUSTOMER_QUERY = """
mutation updateCustomer($input: CustomerInput!) {
  customerUpdate(input: $input) {
    customer {
      id
      firstName
      lastName
      email
      phone
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

GET_SHOPIFY_DATA = """
query {
  shop {
    name
    email
    myshopifyDomain
    plan {
      displayName
    }
    primaryDomain {
      url
      host
    }
  }
}
"""
GET_TOTAL_CUSTOMERS_NR = """
    query CustomerCount {
  customersCount {
    count
  }
}
    """


GET_ALL_PRODUCTS = """
    query getProducts($first: Int, $after: String) {
      products(first: $first, after: $after) {
        edges {
          node {
            id
            title
            descriptionHtml
            handle
            createdAt
            updatedAt
            variants(first: 10) {
              edges {
                node {
                  id
                  title
                  price
                  sku
                }
              }
            }
            images(first: 1) {
              edges {
                node {
                  src
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """


GET_PRODUCTS_INVENTORY = """
query getProductsWithInventory($first: Int = 10) {
  products(first: $first) {
    edges {
      node {
        id
        title
        handle
        variants(first: 10) {
          edges {
            node {
              id
              title
              sku
              inventoryQuantity
            }
          }
        }
      }
    }
  }
}"""


GET_PRODUCT_INVENTORY = """

query getProductInventory($id: ID!) {
  product(id: $id) {
    id
    title
    variants(first: 50) {
      edges {
        node {
          id
          title
          sku
          inventoryQuantity
        }
      }
    }
  }
}"""
