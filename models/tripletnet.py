import chainer
from chainer import cuda
from chainer import functions as F
from chainer import links as L

import numpy as np

from functions.l2_norm_squared import l2_norm_squared
from functions.l2_distance_squared import l2_distance_squared
from models.hoffer_dnn import HofferDnn
from models.embednet_dnn import DnnComponent


class TripletNet(chainer.Chain):
    """
    A triplet network remodelling the network proposed in
    Hoffer, E., & Ailon, N. (2014). Deep metric learning using Triplet network.

    The DNN to be used can be passed to the constructor, keeping it inter-
    changeable.
    """

    def __init__(self):
        super(TripletNet, self).__init__(
            dnn=HofferDnn(),
        )

    def __call__(self, x, compute_acc=False):
        """
        Forward through DNN and compute loss and accuracy.

        x is a batch of size 3n following the form:

        | anchor_1   |
        | [...]      |
        | anchor_n   |
        | positive_1 |
        | [...]      |
        | positive_n |
        | negative_1 |
        | [...]      |
        | negative_n |
        """

        # The batch is forwarded through the network as a whole and then split
        # to 3 batches of size n, which are the input for the triplet_loss

        # forward batch through deep network
        h = self.dnn(x)
        h = F.reshape(h, (h.data.shape[0], h.data.shape[1]))

        # split to anchors, positives, and negatives
        anc, pos, neg = F.split_axis(h, 3, 0)
        n = anc.data.shape[0]

        # compute distances of anchor to positive and negative, respectively
        # diff_pos2 = anc - pos
        # dist_pos2 = F.reshape(l2_norm_squared(diff_pos2), (n, 1))
        # diff_neg = anc - neg
        # dist_neg = F.reshape(l2_norm_squared(diff_neg), (n, 1))
        dist_pos = F.log(F.reshape(l2_distance_squared(anc, pos), (n, 1)))
        dist_neg = F.log(F.reshape(l2_distance_squared(anc, neg), (n, 1)))

        dist = F.concat((dist_pos, dist_neg))

        # compute loss:
        # calculate softmax on distances as a ratio measure
        # loss is MSE of softmax to [0, 1] vector
        sm = F.softmax(dist)
        # TODO generalize to allow gpu -- get_array_module always gives numpy
        # xp = cuda.get_array_module(sm)
        zero_one = cuda.cupy.array([0, 1] * n, dtype=dist.data.dtype).reshape(n, 2)
        self.loss = F.mean_squared_error(sm, chainer.Variable(zero_one))

        if compute_acc:
            self.accuracy = (dist_pos.data < dist_neg.data).sum() / len(dist_pos)

        return self.loss
