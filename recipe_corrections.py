from recipe_parser import extract_recipe_structure
from ingredient_line_parser import parse_ingredient_line
from recipe_ingredient_pipeline import process_recipe


def apply_recipe_corrections(result: dict, corrections: dict, matcher) -> dict:
    """
    Apply user corrections to recipe pipeline results.
    
    Args:
        result (dict): Output from process_recipe()
        corrections (dict): Mapping of raw ingredient → corrected ingredient name
        matcher: IngredientMatcher instance
        
    Returns:
        dict: Updated result with corrections applied
    """
    # Create a copy of the result to avoid modifying the original
    result_copy = {
        "recipe_name": result["recipe_name"],
        "ingredients": [],
        "confidence": result["confidence"]
    }
    
    # Process each ingredient
    for ingredient in result["ingredients"]:
        # Get original parsed ingredient
        original_ingredient = ingredient["parsed"]["ingredient"]
        
        # Check if correction exists
        if original_ingredient in corrections:
            # Get corrected value
            corrected_value = corrections[original_ingredient]
            
            # Update parsed ingredient
            ingredient["parsed"]["ingredient"] = corrected_value
            
            # Re-run matcher with corrected value
            try:
                match_result = matcher.match_ingredient(
                    candidate=corrected_value,
                    context={},
                    generate_proposals=False
                )
                ingredient["match"] = match_result
            except Exception as e:
                ingredient["match"] = {"error": str(e)}
        
        # Add to result copy
        result_copy["ingredients"].append(ingredient.copy())
    
    return result_copy


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
    
    # Define corrections
    corrections = {
        "onion chopped": "onion",
        "salt": "salt"
    }
    
    # Apply corrections
    corrected_result = apply_recipe_corrections(result, corrections, mock_matcher)
    
    # Print BEFORE and AFTER clearly
    print("BEFORE CORRECTIONS:")
    print("=" * 50)
    for i, ingredient in enumerate(result["ingredients"]):
        print(f"Ingredient {i+1}:")
        print(f"  Raw: {ingredient['raw']}")
        print(f"  Parsed: {ingredient['parsed']}")
        print(f"  Match: {ingredient['match']}")
        print(f"  Review: {ingredient['review']}")
        print()
    
    print("AFTER CORRECTIONS:")
    print("=" * 50)
    for i, ingredient in enumerate(corrected_result["ingredients"]):
        print(f"Ingredient {i+1}:")
        print(f"  Raw: {ingredient['raw']}")
        print(f"  Parsed: {ingredient['parsed']}")
        print(f"  Match: {ingredient['match']}")
        print()