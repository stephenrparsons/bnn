import argparse
import os
import re

from PIL import Image
import rawpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='root data directory')
    parser.add_argument('output', help='directory to place cleaned data')
    args = parser.parse_args()

    images_processed = 0
    for root, dirs, files in os.walk(args.input):
        for f in files:
            if re.match(r'IMG_\d\d\d\d\.CR2', f.upper()):
                original_path = os.path.join(root, f)
                common_path = os.path.commonpath([args.input, original_path])
                relative_path = os.path.relpath(root, common_path)
                new_path = os.path.join(args.output, relative_path, f)
                new_path = os.path.splitext(new_path)[0] + '.png'
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                print(new_path)
                # Read raw image
                raw = rawpy.imread(original_path)
                # Convert to PIL Image
                img = Image.fromarray(raw.postprocess())
                # Convert to RGB
                img = img.convert('RGB')
                # Flip right side up
                img = img.transpose(Image.ROTATE_180)
                # Save to new file
                img.save(new_path)
                images_processed += 1
        for d in dirs:
            if 'copy' in d.lower():
                dirs.remove(d)
    print(f'Number of images processed: {images_processed}')


if __name__ == '__main__':
    main()
