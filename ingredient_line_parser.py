def parse_ingredient_line(line: str) -> dict:
    """
    Parse an ingredient line into ingredient name, quantity, and unit.
    
    Args:
        line (str): Raw ingredient line text
        
    Returns:
        dict: Dictionary with ingredient, quantity, and unit
    """
    # Remove extra whitespace
    line = line.strip()
    
    # Handle empty lines
    if not line:
        return {
            "ingredient": "",
            "quantity": None,
            "unit": None
        }
    
    # Define units
    units = {"g", "kg", "ml", "l", "cup", "cups", "tbsp", "tsp"}
    
    # Simple approach: check for unit immediately following a number
    import re
    
    # Pattern to match number followed by unit (e.g., "500g", "1.5kg")
    # This handles cases like "500g minced beef" 
    unit_pattern = r'^(\d+(?:\.\d+)?)\s*(cups|cup|kg|g|ml|l|tbsp|tsp)\s*(.*)$'
    
    match = re.match(unit_pattern, line)
    if match:
        quantity = float(match.group(1))
        unit = match.group(2)
        ingredient = match.group(3).strip()
        # If ingredient is empty, set it to empty string
        if not ingredient:
            ingredient = ""
    else:
        # Fallback to word-based parsing
        words = line.split()
        
        # Initialize return values
        quantity = None
        unit = None
        ingredient = ""
        
        # Check if first word is a number
        if words and words[0].replace('.', '', 1).isdigit():
            # Parse quantity
            try:
                quantity = float(words[0])
                # Remove quantity from words
                words = words[1:]
            except ValueError:
                # If not a valid number, treat as ingredient
                pass
        
        # Check if first word (after quantity removal) is a unit
        if words and words[0].lower() in units:
            unit = words[0].lower()
            # Remove unit from words
            words = words[1:]
        
        # Everything else is ingredient name
        if words:
            ingredient = " ".join(words)
        else:
            # If no words left after processing, use original line
            ingredient = line
    
    return {
        "ingredient": ingredient,
        "quantity": quantity,
        "unit": unit
    }


# Simple test
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "500g minced beef",
        "2 cups flour", 
        "salt",
        "1.5 kg sugar",
        "3 tbsp oil",
        "250 ml milk",
        "1 cup sugar",
        "100g butter",
        "1 tsp vanilla extract"
    ]
    
    for test in test_cases:
        result = parse_ingredient_line(test)
        print(f"'{test}' → {result}")