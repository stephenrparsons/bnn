import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import bnn_util
import json


def restore_model(run):
    # load opts used during training
    opts = json.loads(open("ckpts/%s/opts.json" % run).read())

    # NOTE: we construct this model with unspecified width/height so we can pass in anything
    model = construct_model(
        width=None,
        height=None,
        use_skip_connections=not opts['no_use_skip_connections'],
        base_filter_size=opts['base_filter_size'],
        use_batch_norm=not opts['no_use_batch_norm']
    )

    # restore weights from latest checkpoint
    latest_ckpt = bnn_util.latest_checkpoint_in_dir("ckpts/%s" % run)
    model.load_weights("ckpts/%s/%s" % (run, latest_ckpt))

    return opts, model


def construct_model(width, height, base_filter_size,
                    use_batch_norm=True, use_skip_connections=True):
    def conv_bn_relu_block(i, _, filters, strides):

        # TODO: try this as more theoretically correct approach
        #    o = Conv2D(filters=filters, kernel_size=3,
        #               strides=strides, padding='same',
        #               use_bias=(not use_batch_norm))(i)
        #    if use_batch_norm:
        #      o = BatchNormalization(scale=False)(o)

        o = layers.Conv2D(filters=filters, kernel_size=3,
                          strides=strides, padding='same')(i)
        if use_batch_norm:
            o = layers.BatchNormalization()(o)

        # TODO: try BN after relu
        return layers.ReLU()(o)

    inputs = layers.Input(shape=(height, width, 3), name='inputs')

    e1 = conv_bn_relu_block(inputs, 'e1', filters=base_filter_size, strides=2)
    e2 = conv_bn_relu_block(e1, 'e2', filters=2 * base_filter_size, strides=2)
    e3 = conv_bn_relu_block(e2, 'e3', filters=4 * base_filter_size, strides=2)
    e4 = conv_bn_relu_block(e3, 'e4', filters=8 * base_filter_size, strides=2)

    # note: using version of keras locally that doesn't support interpolation='nearest' so
    #       unsure what resize is happening here...

    d1 = layers.UpSampling2D(name='e4nn')(e4)
    if use_skip_connections:
        d1 = layers.Concatenate(name='d1_e3')([d1, e3])
    d1 = conv_bn_relu_block(d1, 'd1', filters=4 * base_filter_size, strides=1)

    d2 = layers.UpSampling2D(name='d1nn')(d1)
    if use_skip_connections:
        d2 = layers.Concatenate(name='d2_e2')([d2, e2])
    d2 = conv_bn_relu_block(d2, 'd2', filters=2 * base_filter_size, strides=1)

    d3 = layers.UpSampling2D(name='d2nn')(d2)
    if use_skip_connections:
        d3 = layers.Concatenate(name='d3_e1')([d3, e1])
    d3 = conv_bn_relu_block(d3, 'd3', filters=base_filter_size, strides=1)

    logits = layers.Conv2D(filters=1, kernel_size=1, strides=1,
                           activation=None, name='logits')(d3)

    return keras.Model(inputs=inputs, outputs=logits)


def compile_model(model, learning_rate, pos_weight=1.0):
    def weighted_xent(y_true, y_predicted):
        return tf.reduce_mean(
            tf.nn.weighted_cross_entropy_with_logits(
                labels=y_true,
                logits=y_predicted,
                pos_weight=pos_weight
            )
        )

    model.compile(optimizer=tf.optimizers.Adam(learning_rate=learning_rate),
                  loss=weighted_xent)
    return model
