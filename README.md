# Bedbug detector

This project is designed to automatically detect bedbugs from a particular
experimental capture setup. The code is based on Mat Kelcey's "BNN" for
detecting bees in images.

I (Stephen) have made some initial changes:

- `requirements.txt` now has specific non-conflicting versions of everything
- `label_ui.py` adjusts to different image sizes and allows zoom/pan
(also the graphics framework was changed).

The following example commands show how I have been using this. This depends on
having some readable (not raw) images in the `image-dir` directory, in the below case
`data/images/2020-04 60D/png`. I have images on my machine in the `data/images`
directory, but they don't get uploaded to the repository since I instructed
git not to pay attention to that directory using the file `.gitignore`.

```
$ virtualenv -p python3 venv
$ . venv/bin/activate
(venv) $ pip install -r requirements.txt
(venv) $ python label_ui.py --image-dir data/images/2020-04\ 60D/png --label-db data/labels.db
```

## TODO

- [x] allow images of different sizes
- [x] allow zoom/pan
- [x] switch from tkinter to PyQt5 since tkinter [being weird](https://bugs.python.org/issue42480)
- [x] support raw images
- [x] decide for raw images: flip them over on disk? (yes) ~~if not, store their label coordinates flipped or not?~~
- [x] initial data processing: flip raw images, convert to png
- [x] support labeling of tick marks
- [x] figure out image directory structure
- [x] switch from TensorFlow 1 to TensorFlow 2
- [ ] have title show how many total bugs exist on images currently open in program
- [x] run initial training example pipeline on GPU machine
- [ ] continue working through example batch script
- [ ] consider modifications such that nobody has to locally download the images
