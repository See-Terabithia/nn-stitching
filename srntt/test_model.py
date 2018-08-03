import numpy as np
import tensorflow as tf

import Vgg_module
import utils
import patch_match
import ce_model
import ctt_model
import vgg19
import dataload

def Gram(feature_maps):
  """Computes the Gram matrix for a set of feature maps."""
  batch_size, height, width, channels = tf.unstack(tf.shape(feature_maps))
  #denominator = tf.to_float(height * width)
  feature_maps = tf.reshape(
      feature_maps, tf.stack([batch_size, height * width, channels]))
  matrix = tf.matmul(feature_maps, feature_maps, adjoint_a=True)
  return matrix #/denominator

imgNo = 10
batchSize=5
path = "..."
train_ref, train_hr = dataload.dataLoader(path)
train_lr = utils.img_resize(train_hr, 25)
train_lref = utils.img_resize(train_ref, 25)

M_LR = Vgg_module.vgg19_module(utils.img_resize(train_lr, 400))
M_LRef = Vgg_module.vgg19_module(utils.img_resize(train_lref, 400))
M_Ref = Vgg_module.vgg19_module(train_ref)

M_t = np.zeros(M_LR.shape)
M_s = np.zeros(M_LR.shape)
for i in range(M_LR.shape[0]):
    M_t[i,:,:,:], M_s[i,:,:,:] = patch_match.Fun_patchMatching(M_LR[i,:,:,:], M_LRef[i,:,:,:], M_Ref[i,:,:,:])

with tf.Session(config=tf.ConfigProto(gpu_options=(tf.GPUOptions(per_process_gpu_memory_fraction=0.5)))) as sess:
 
    x = tf.placeholder(tf.float32, [None, 40, 40, 3])
    y = tf.placeholder(tf.float32, [None, 160, 160, 3])
    Mt_ph= tf.placeholder(tf.float32, [None, 40, 40, 256])
    Ms_ph= tf.placeholder(tf.float32, [None, 40, 40, 256])
    train_mode = tf.placeholder(tf.bool)
    Learning_rate = tf.placeholder(tf.float32, shape=[])

    ce_net = ce_model.CE(x, train_mode)
    y_pred = ctt_model.CTT(ce_net, Mt_ph, train_mode)

    vgg = vgg19.Vgg19()
    vgg.build(y)
    vgg_y = vgg.conv5_1

    vgg2 = vgg19.Vgg19()
    vgg2.build(y_pred)
    y_pred_conv31 = vgg2.conv3_1
    y_pred_conv51 = vgg2.conv5_1

    loss = tf.norm(y-y_pred, ord=1)/(160.*160.)
    loss_total = tf.norm(y-y_pred, ord=1)/(160.*160.) + 1e-4 * tf.norm(vgg_y-y_pred_conv51, ord=2)/512./100. \
    + 1e-4 * tf.norm(Gram(y_pred_conv31*Ms_ph)-Gram(Mt_ph), ord=2)/(1600.*2.*256.)**2

    optimizer = tf.train.AdamOptimizer(learning_rate=Learning_rate)    
    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    with tf.control_dependencies(update_ops):
        train_op_pre = optimizer.minimize(loss)
        train_op = optimizer.minimize(loss_total)

    init = tf.global_variables_initializer()
    sess.run(init)

    for epoch in range(1000):
        ran=np.sort(np.random.choice(train_lr.shape[0],batchSize,replace=False))
        xbatch = train_lr[ran,:,:,:]
        ybatch = train_hr[ran,:,:,:]
        MtBatch = M_t[ran,:,:,:]
        MsBatch = M_s[ran,:,:,:]
        learning_rate = 1e-4
        if epoch > 5:
            sess.run(train_op, feed_dict={x:xbatch, y:ybatch, Mt_ph:MtBatch, Ms_ph:MsBatch,train_mode:True, Learning_rate: learning_rate})
        else:
            sess.run(train_op_pre, feed_dict={x:xbatch, y:ybatch, Mt_ph:MtBatch, Ms_ph:MsBatch,train_mode:True, Learning_rate: learning_rate})
        if epoch % 50==0:
            # update learning rate
            learning_rate /= 10
            print(sess.run(loss_total, feed_dict={x:xbatch, y:ybatch, Mt_ph:MtBatch, Ms_ph:MsBatch, train_mode:False}))
            prediction = sess.run(y_pred, feed_dict = {x:train_lr, Mt_ph:M_t, train_mode:False})
            # Calculate or Save the prediction

