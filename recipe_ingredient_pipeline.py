from recipe_parser import extract_recipe_structure
from ingredient_line_parser import parse_ingredient_line

def process_recipe(text: str, matcher) -> dict:
    """
    Process a recipe text through the parsing and matching pipeline.
    
    Args:
        text (str): Raw recipe text
        matcher: IngredientMatcher instance
        
    Returns:
        dict: Processed recipe with ingredients and matches
    """
    # Step 1: Extract recipe structure
    recipe_structure = extract_recipe_structure(text)
    
    # Initialize result structure
    result = {
        "recipe_name": recipe_structure["recipe_name"],
        "ingredients": [],
        "confidence": recipe_structure["confidence"]
    }
    
    # Step 2 & 3: Process each ingredient line
    for ingredient_line in recipe_structure["ingredients_raw"]:
        parsed_ingredient = parse_ingredient_line(ingredient_line)

        if not parsed_ingredient["ingredient"]:
            continue

        try:
            match_result = matcher.match_ingredient(
                candidate=parsed_ingredient["ingredient"],
                context={},
                generate_proposals=False
            )
        except Exception as e:
            match_result = {"error": str(e)}

        # Add review flags
        review_flags = {
            "missing_quantity": parsed_ingredient["quantity"] is None,
            "missing_unit": parsed_ingredient["unit"] is None,
            "low_confidence": (
                match_result.get("confidence", 1.0) < 0.85 
                if "confidence" in match_result else False
            ),
            "needs_review": False  # Will be set below
        }
        
        # Determine if needs_review
        review_flags["needs_review"] = (
            review_flags["missing_quantity"] or 
            review_flags["missing_unit"] or 
            review_flags["low_confidence"]
        )
        
        ingredient_entry = {
            "raw": ingredient_line,
            "parsed": parsed_ingredient,
            "match": match_result,
            "review": review_flags
        }

        result["ingredients"].append(ingredient_entry)
    
    return result


# Simple test
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
    
    # Test with clean recipe
    print("=== Testing Clean Recipe ===")
    sample_recipe_clean = """Chocolate Chip Cookies
Ingredients:
1 cup butter
2 cups sugar
3 cups flour
1 tsp vanilla extract
Method:
Preheat oven to 350°F
Mix ingredients together
Bake for 12 minutes"""
    
    # Test the pipeline
    mock_matcher = MockMatcher()
    result = process_recipe(sample_recipe_clean, mock_matcher)
    
    print("Recipe Processing Result:")
    print(f"Recipe Name: {result['recipe_name']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Number of ingredients: {len(result['ingredients'])}")
    
    for i, ingredient in enumerate(result['ingredients']):
        print(f"\nIngredient {i+1}:")
        print(f"  Raw: {ingredient['raw']}")
        print(f"  Parsed: {ingredient['parsed']}")
        print(f"  Match: {ingredient['match']}")
        print(f"  Review: {ingredient['review']}")
    
    # Test with messy real-world input
    print("\n=== Testing Messy Real-World Input ===")
    sample_recipe_messy = """
Chicken Curry

500g chicken breast
1 onion chopped
2 tbsp oil
salt

Cook chicken
Add onion
"""
    
    result2 = process_recipe(sample_recipe_messy, mock_matcher)
    
    print("Recipe Processing Result:")
    print(f"Recipe Name: {result2['recipe_name']}")
    print(f"Confidence: {result2['confidence']}")
    print(f"Number of ingredients: {len(result2['ingredients'])}")
    
    for i, ingredient in enumerate(result2['ingredients']):
        print(f"\nIngredient {i+1}:")
        print(f"  Raw: {ingredient['raw']}")
        print(f"  Parsed: {ingredient['parsed']}")
        print(f"  Match: {ingredient['match']}")
        print(f"  Review: {ingredient['review']}")
