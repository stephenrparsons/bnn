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
- [ ] have title show how many total bugs exist on images currently open in program
- [ ] run initial training example pipeline on GPU machine

The original README from Mat's bee project is below.

# BNN v2

unet style image translation from image of hive entrance to bitmap of location of center of bees.

trained in a semi supervised way on a desktop gpu and deployed to run in real time on the hive using
either a [raspberry pi](https://www.raspberrypi.org/) using a [neural compute stick](https://developer.movidius.com/)
or a [je vois embedded smart camera](http://jevois.org/)

see [this blog post](http://matpalm.com/blog/counting_bees/) for more info..

here's an example of predicting bee position on some held out data. the majority of examples trained had ~10 bees per image.

![rgb_labels_predictions.png](rgb_labels_predictions.png)

the ability to locate each bee means you can summarise with a count. note the spike around 4pm when the bees at this time of year come back to base.

![counts_over_days.png](counts_over_days.png)

## usage

see `run_sample_training_pipeline.sh` for an executable end to end smoke test walkthrough of these steps (using sample data)

### dependencies

code depends in `requirements.txt`

```
sudo apt-get install python3-tk python3-pil python3-pil.imagetk
sudo pip3 install -r requirements.txt
```

### gathering data

the `rasp_pi` sub directory includes one method of collecting images on a raspberry pi.

### labelling

start by using the `label_ui.py` tool to manually label some images and create a sqlite `label.db`

the following command starts the labelling tool for some already labelled (by me!) sample data provided with in this repro.

```
./label_ui.py \
--image-dir sample_data/training/ \
--label-db sample_data/labels.db \
--width 768 --height 1024
```

hints

* left click to label the center of a bee
* right click to remove the closest label
* press up to toggle labels on / off. this can help in tricky cases.
* use left / right to move between images. it's often helpful when labelling to quickly switch back/forth between images to help distinguish background
* use whatever system your OS provides to zoom in; e.g. in ubuntu super+up / down

you can merge entries from `a.db` into `b.db` with `merge_db.py`

```
./merge_dbs.py --from-db a.db --into-db b.db
```

### training

before training we materialise a `label.db` (which is a database of x,y coords)
into black and white bitmaps using `./materialise_label_db.py`

```
./materialise_label_db.py \
--label-db sample_data/labels.db \
--directory sample_data/labels/ \
--width 768 --height 1024
```

we can visualise the training data with `data.py`. this will generate a number of `test*png` files with
the input data on the left (with data augmentation) and the output labels on the right.

```
./data.py \
--image-dir sample_data/training/ \
--label-dir sample_data/labels/ \
--width 768 --height 1024
```

![sample_data/test_002_001.png](sample_data/test_002_001.png)

train with `train.py`.

`run` denotes the subdirectory for ckpts and tensorboard logs; e.g. `--run r12` checkpoints
under `ckpts/r12/` and logs under `tb/r12`.

use `--help` to get complete list of options including model config, defining validation data and stopping conditions.

e.g. to train for a short time on `sample_data` run the following... (for a more realistic result we'd want
to train for many more steps on much more data)

```
./train.py \
--run r12 \
--steps 300 \
--train-steps 50 \
--train-image-dir sample_data/training/ \
--test-image-dir sample_data/test/ \
--label-dir sample_data/labels/ \
--width 768 --height 1024
```

progress can be visualised with tensorboard (serves at <a href="http://localhost:6006">localhost:6006</a>)

```
tensorboard --log-dir tb
```

### inference

predictions can be run with `predict.py`.
to specifiy what type of output set one of the following...

* `--output-label-db` to create a label db; this can be merged with a human labelled db, using `./merge_dbs.py` for semi supervised learning
* `--export-pngs centroids` to export output bitmaps equivalent as those made by `./materialise_label_db.py`
* `--export-pngs predictions` to export explicit model output (i.e. before connected components post processing)

<b>NOTE: given the above step that only runs a short period on a small dataset we DON'T expect this to give
a great result; these instructions are more included to prove the plumbing works...</b>

```
./predict.py \
--run r12 \
--image-dir sample_data/unlabelled \
--output-label-db sample_predictions.db \
--export-pngs predictions
```

output predictions can be compared to labelled data to calculate precision recall.
(we deem a detection correct if it is within a thresholded distance from a label)

```
./compare_label_dbs.py --true-db ground_truth.db --predicted-db predictions.db
precision 0.936  recall 0.797  f1 0.861
```

### running on compute stick

after loads of hacking i did eventually get this running on the compute stick.
some info is included in [this issue](https://github.com/matpalm/bnn/issues/8)
with additional background info in [this forum post](https://ncsforum.movidius.com/discussion/692/incorrect-inference-results-from-a-minimal-tensorflow-model#latest)

[update] given how long ago this was, i'm hoping things are easier these days :D

### some available datasets

* [Jonathan Byrne's](https://github.com/squeakus) [to-bee-or-not-to-bee](https://www.kaggle.com/jonathanbyrne/to-bee-or-not-to-bee) kaggle dataset
