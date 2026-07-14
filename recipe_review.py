from recipe_parser import extract_recipe_structure
from ingredient_line_parser import parse_ingredient_line
from recipe_ingredient_pipeline import process_recipe


def format_recipe_review(result: dict) -> list:
    """
    Convert recipe pipeline output into a clean review format.
    
    Args:
        result (dict): Result from process_recipe()
        
    Returns:
        list: List of review entries with ingredient status and issues
    """
    review_entries = []
    
    for ingredient in result["ingredients"]:
        # Get ingredient name from parsed data
        ingredient_name = ingredient["parsed"]["ingredient"]
        
        # Get review flags
        review_flags = ingredient["review"]
        
        # Build issues list
        issues = []
        if review_flags["missing_quantity"]:
            issues.append("missing_quantity")
        if review_flags["missing_unit"]:
            issues.append("missing_unit")
        if review_flags["low_confidence"]:
            issues.append("low_confidence")
        
        # Determine status
        status = "ok" if len(issues) == 0 else "needs_review"
        
        # Build review entry
        review_entry = {
            "ingredient": ingredient_name,
            "status": status,
            "issues": issues
        }
        
        review_entries.append(review_entry)
    
    return review_entries


# Test
if __name__ == "__main__":
    # Create a mock matcher for testing
    class MockMatcher:
        def match_ingredient(self, candidate, context, generate_proposals=False):
            return {
                "matched": True,
                "ingredient_name": candidate,
                "confidence": 0.95,
                "supplier": "Test Supplier"
            }
    
    # Test with messy real-world input
    sample_recipe_messy = """
Chicken Curry

500g chicken breast
1 onion chopped
2 tbsp oil
salt

Cook chicken
Add onion
"""
    
    # Process recipe
    mock_matcher = MockMatcher()
    result = process_recipe(sample_recipe_messy, mock_matcher)
    
    # Format review
    review = format_recipe_review(result)
    
    # Print output clearly
    print("Recipe Review:")
    print("=" * 50)
    for entry in review:
        print(f"Ingredient: {entry['ingredient']}")
        print(f"Status: {entry['status']}")
        if entry['issues']:
            print(f"Issues: {', '.join(entry['issues'])}")
        else:
            print("Issues: None")
        print("-" * 30)