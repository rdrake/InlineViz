from PIL import Image, ImageDraw

#This merges two image files using PIL
def merge_images(image1, image2, orientation):
    """Merge two images into one, displayed above and below
    :param image1: PIL object
    :param image2: PIL object
    :return: the merged Image object
    """
    (width1, height1) = image1.size
    (width2, height2) = image2.size
    
    mask1 = image1.convert("RGBA")
    mask2 = image2.convert("RGBA")

    if orientation == "vertical":

        result_width = max(width1, width2)
        result_height = height1 + height2

        result = Image.new('RGB', (result_width, result_height))
        result.paste(image1, (0, 0), mask1)        
        result.paste(image2, (0, height1), mask2)

    elif orientation == "horizontal":     

        result_width = width1 + width2
        result_height = max(height1, height2)

        result = Image.new('RGB', (result_width, result_height))
        result.paste(image1, (0, 0), mask1)        
        result.paste(image2, (width1, 0), mask2)
    
    return result