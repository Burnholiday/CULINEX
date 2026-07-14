def extract_recipe_structure(text: str) -> dict:
    """
    Extract recipe structure from text content.
    
    Args:
        text (str): Raw text content containing recipe information
        
    Returns:
        dict: Recipe structure with name, ingredients, method, and confidence
    """
    # Split text into lines and remove empty lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return {
            "recipe_name": "",
            "ingredients_raw": [],
            "method_raw": [],
            "confidence": 0.4
        }

    def clean_line(line):
        return line.lstrip("-• ").strip()

    # Recipe name
    recipe_name = ""
    for line in lines:
        if len(line) <= 80 and not any(char.isdigit() for char in line[:10]):
            recipe_name = line
            break
    
    ingredients_start = -1
    method_start = -1

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if "ingredient" in line_lower and ingredients_start == -1:
            ingredients_start = i + 1

        elif any(k in line_lower for k in ["method", "instruction", "direction"]) and method_start == -1:
            method_start = i + 1

    ingredients_raw = []
    method_raw = []

    if ingredients_start != -1 and method_start != -1:
        ingredients_raw = [clean_line(l) for l in lines[ingredients_start:method_start - 1]]
        method_raw = [clean_line(l) for l in lines[method_start:]]
        confidence = 0.9

    elif ingredients_start != -1:
        ingredients_raw = [clean_line(l) for l in lines[ingredients_start:]]
        confidence = 0.6

    elif method_start != -1:
        method_raw = [clean_line(l) for l in lines[method_start:]]
        confidence = 0.6

    else:
        # Fallback: detect ingredient-like lines instead of splitting blindly
        ingredients_raw = []
        method_raw = []

        # Define method verbs to distinguish instructions from ingredients
        method_verbs = [
            "add", "cook", "mix", "stir", "heat", "bake",
            "fry", "boil", "grill", "combine", "pour"
        ]

        for line in lines[1:]:  # skip recipe name
            line_lower = line.lower()

            # Heuristic: ingredient lines usually contain:
            # - numbers OR
            # - common units OR
            # - short descriptive phrases (3 words or less) that aren't method verbs
            line_words = line_lower.split()
            is_method_instruction = any(verb in line_words for verb in method_verbs)
            
            if (
                any(char.isdigit() for char in line) or
                any(unit in line_lower for unit in ["g", "kg", "ml", "l", "cup", "tbsp", "tsp"]) or
                (len(line.split()) <= 3 and not is_method_instruction)
            ):
                ingredients_raw.append(clean_line(line))
            else:
                method_raw.append(clean_line(line))

        confidence = 0.4

    return {
        "recipe_name": recipe_name,
        "ingredients_raw": ingredients_raw,
        "method_raw": method_raw,
        "confidence": confidence
    }


# Simple test
if __name__ == "__main__":
    # Test with sample recipe text
    sample_text = """Chocolate Chip Cookies
Ingredients:
1 cup butter
2 cups sugar
3 cups flour
Method:
Preheat oven to 350°F
Mix ingredients together
Bake for 12 minutes"""
    
    result = extract_recipe_structure(sample_text)
    print("Recipe Structure:")
    print(f"Name: {result['recipe_name']}")
    print(f"Ingredients: {result['ingredients_raw']}")
    print(f"Method: {result['method_raw']}")
    print(f"Confidence: {result['confidence']}")