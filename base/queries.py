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
    query getProducts($first: Int, $after: String, $query:String) {
      products(first: $first, after: $after,query:$query) {
        edges {
          node {
            id
            title
            descriptionHtml
            handle
            createdAt
            updatedAt
            hasOutOfStockVariants
            isGiftCard
            publishedAt
            tags
            totalInventory
            variantsCount {
              count
              precision
            }
            variants(first: $first) {
              edges {
                node {
                  id
                  title
                  price
                  inventoryQuantity
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

GET_PRODUCT = """
query getProductById($id: ID!) {
  product(id: $id) {
    id
    title
    descriptionHtml
    handle
    createdAt
    updatedAt
    hasOutOfStockVariants
    isGiftCard
    publishedAt
    tags
    totalInventory
    variantsCount {
      count
      precision
    }
    variants(first: 50) {
      edges {
        node {
          id
          title
          price
          sku
          inventoryQuantity
        }
      }
    }
    images(first: 5) {
      edges {
        node {
          src
        }
      }
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


GET_CUSTOMERS_ORDERS = """
query getCustomerOrders($customerId: ID!, $first: Int = 10) {
  customer(id: $customerId) {
    id
    firstName
    lastName
    orders(first: $first) {
      edges {
        node {
          id
          name
          createdAt
          lineItems(first: $first) {
            edges {
              node {
                title
                product {
                  id
                  title
                }
                quantity
              }
            }
          }
        }
      }
    }
  }
}
"""


GET_SHOP_INFO = """
query {
  shop {
    id
    name
    email
    myshopifyDomain
    shopOwnerName
    primaryDomain {
      url
      host
    }
  }
}
"""


GET_SHOP_ORDERS = """
query getOrders($first: Int = 10, $after: String) {
  orders(first: $first, after: $after) {
    edges {
      node {
        id
        name
        createdAt
        totalPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
        customer {
          id
          firstName
          lastName
          email
        }
        lineItems(first: 10) {
          edges {
            node {
              quantity
              restockable
              product {
                id
                title
              }
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


CREATE_CHARGE = """mutation AppSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $test: Boolean = false) {
    appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems, test: $test) {
      userErrors {
        field
        message
      }
      appSubscription {
        id
      }
      confirmationUrl
    }
  }"""

CURRENT_CHARGE = """query {
  currentAppInstallation {
    activeSubscriptions {
      id
      name
      status
      createdAt
      currentPeriodEnd
      lineItems {
        plan {
          pricingDetails {
            ... on AppRecurringPricing {
              price {
                amount
                currencyCode
              }
              interval
            }
          }
        }
      }
    }
  }
}"""

GET_SHOPIFY_CHARGE = """query {
  currentAppInstallation {
    appSubscriptions(first: 10) {
      edges {
        node {
          id
          name
          status
          createdAt
          lineItems {
            plan {
              pricingDetails {
                ... on AppRecurringPricing {
                  price {
                    amount
                    currencyCode
                  }
                  interval
                }
              }
            }
          }
        }
      }
    }
  }
}"""
