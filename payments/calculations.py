def recommend_package(messages, customers, budget, is_business):
    # Define threshold values
    BASIC_THRESHOLD_CUSTOMERS = 100
    SILVER_THRESHOLD_CUSTOMERS = 1000
    GOLD_THRESHOLD_CUSTOMERS = 5000

    BASIC_THRESHOLD_MESSAGES = 1000
    SILVER_THRESHOLD_MESSAGES = 2500
    GOLD_THRESHOLD_MESSAGES = 5000

    BASIC_THRESHOLD_BUDGET = 500
    SILVER_THRESHOLD_BUDGET = 1500
    GOLD_THRESHOLD_BUDGET = 3000

    # Initialize scores for each package
    basic_score = 0
    silver_score = 0
    gold_score = 0

    # Evaluate based on the number of messages
    if messages <= BASIC_THRESHOLD_MESSAGES:
        basic_score += 1
    elif messages <= SILVER_THRESHOLD_MESSAGES:
        silver_score += 1
    else:
        gold_score += 1

    # Evaluate based on the number of customers
    if customers <= BASIC_THRESHOLD_CUSTOMERS:
        basic_score += 1
    elif customers <= SILVER_THRESHOLD_CUSTOMERS:
        silver_score += 1
    else:
        gold_score += 1

    # Evaluate based on the budget
    if budget <= BASIC_THRESHOLD_BUDGET:
        basic_score += 1
    elif budget <= SILVER_THRESHOLD_BUDGET:
        silver_score += 1
    else:
        gold_score += 1

    # Evaluate based on business status
    if is_business:
        silver_score += 1
        gold_score += 1

    # Determine the recommended package
    if max(basic_score, silver_score, gold_score) == basic_score:
        return "BASIC PLAN"
    elif max(basic_score, silver_score, gold_score) == silver_score:
        return "SILVER PLAN"
    else:
        return "GOLD PLAN"

# Example usage:
messages = 1500
customers = 500
budget = 1000
is_business = True

recommended_package = recommend_package(messages, customers, budget, is_business)
print(f"Recommended Package: {recommended_package}")
