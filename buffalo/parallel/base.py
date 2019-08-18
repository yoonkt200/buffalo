# -*- coding: utf-8 -*-
import abc

import numpy as np

from buffalo.algo.als import ALS
from buffalo.algo.cfr import CFR
from buffalo.algo.w2v import W2V
from buffalo.algo.bpr import BPRMF

from buffalo.parallel._core import dot_topn


class Parallel(abc.ABC):
    def __init__(self, algo, *argv, **kwargs):
        super().__init__()
        if not isinstance(algo, (ALS, CFR, W2V, BPRMF)):
            raise ValueError('Not supported algo type: %s' % type(algo))
        self.algo = algo
        self.num_workers = int(kwargs['num_workers'])

    def _most_similar(self, indexes, Factor, topk, pool):
        out_keys = np.zeros(shape=(len(indexes), topk), dtype=np.int32)
        out_scores = np.zeros(shape=(len(indexes), topk), dtype=np.float32)
        dot_topn(indexes, Factor, Factor, out_keys, out_scores, pool, topk, self.num_workers)
        return out_keys, out_scores

    def _most_similar_bias(self, indexes, Factor, Bias, topk, pool):
        pass

    @abc.abstractmethod
    def most_similar(self, keys, topk=10, group='item', pool=None, repr=False):
        """Caculate TopK most similar items for each keys in parallel processing.

        :param list keys: Query Keys
        :param int topk: Number of topK
        :param str group: Data group where to find (default: item)
        :param pool: The list of item keys to find for.
            If it is a numpy.ndarray instance then it treat as index of items and it would be helpful for calculation speed. (default: None)
        :type pool: list or numpy.ndarray
        :param bool repr: Set True, to return as item key instead index.
        :return: list of tuple(key, score)
        """
        raise NotImplemented

    def _topk_recommendation(self, indexes, FactorP, FactorQ, topk, pool):
        out_keys = np.zeros(shape=(len(indexes), topk), dtype=np.int32)
        out_scores = np.zeros(shape=(len(indexes), topk), dtype=np.float32)
        dot_topn(indexes, FactorP, FactorQ, out_keys, out_scores, pool, topk, self.num_workers)
        return out_keys, out_scores

    def _topk_recommendation_bias(self, indexes, FactorP, FactorQ, FactorQb, topk, pool):
        pass

    @abc.abstractmethod
    def topk_recommendation(self, keys, topk=10, pool=None, repr=False):
        """Caculate TopK recommendation for each users in parallel processing.

        .. warning::
            It may not works with normalized factors.

        :param list keys: Query Keys
        :param int topk: Number of topK
        :param bool repr: Set True, to return as item key instead index.
        :return: list of tuple(key, score)
        """
        raise NotImplemented


class ParALS(Parallel):
    def __init__(self, algo, **kwargs):
        num_workers = int(kwargs.get('num_workers', algo.opt.num_workers))
        super().__init__(algo, num_workers=num_workers)

    def most_similar(self, keys, topk=10, group='item', pool=None, repr=False):
        """See the documentation of Parallel."""
        self.algo.normalize(group=group)
        indexes = self.algo.get_index_pool(keys, group=group)
        keys = [k for k, i in zip(keys, indexes) if i is not None]
        indexes = np.array([i for i in indexes if i is not None], dtype=np.int32)
        if pool is not None:
            pool = self.algo.get_index_pool(pool, group=group)
            if len(pool) == 0:
                raise RuntimeError('pool is empty')
        else:
            # It assume that empty pool menas for all items
            pool = np.array([], dtype=np.int32)
        if group == 'item':
            topks, scores = super()._most_similar(indexes, self.algo.Q, topk, pool)
            if repr:
                topks = [[self.algo._idmanager.itemids[t] for t in tt if t != -1] for tt in topks]
            return topks, scores
        elif group == 'user':
            topks, scores = super()._most_similar(indexes, self.algo.Q, topk, pool)
            if repr:
                topks = [[self.algo._idmanager.userids[t] for t in tt if t != -1] for tt in topks]
            return topks, scores
        raise ValueError(f'Not supported group: {group}')

    def topk_recommendation(self, keys, topk=10, pool=None, repr=False):
        """See the documentation of Parallel."""
        if self.algo.opt._nrz_P or self.algo.opt._nrz_Q:
            raise RuntimeError('Cannot make topk recommendation with normalized factors')
        # It is possible to skip make recommendation for not-existed keys.
        indexes = self.algo.get_index_pool(keys, group='user')
        keys = [k for k, i in zip(keys, indexes) if i is not None]
        indexes = np.array([i for i in indexes if i is not None], dtype=np.int32)
        if pool is not None:
            pool = self.algo.get_index_pool(pool, group='item')
            if len(pool) == 0:
                raise RuntimeError('pool is empty')
        else:
            # It assume that empty pool menas for all items
            pool = np.array([], dtype=np.int32)
        topks, scores = super()._topk_recommendation(indexes, self.algo.P, self.algo.Q, topk, pool)
        if repr:
            topks = [[self.algo._idmanager.itemids[t] for t in tt if t != -1] for tt in topks]
        return keys, topks, scores


class ParBPRMF(ParALS):
    def topk_recommendation(self, keys, topk=10, pool=None, repr=False):
        raise NotImplemented


class ParW2V(Parallel):
    def __init__(self, algo, **kwargs):
        num_workers = int(kwargs.get('num_workers', algo.opt.num_workers))
        super().__init__(algo, num_workers=num_workers)

    def most_similar(self, keys, topk=10, pool=None, repr=False):
        """See the documentation of Parallel."""
        self.algo.normalize(group='item')
        indexes = self.algo.get_index_pool(keys, group='item')
        keys = [k for k, i in zip(keys, indexes) if i is not None]
        indexes = np.array([i for i in indexes if i is not None], dtype=np.int32)
        if pool is not None:
            pool = self.algo.get_index_pool(pool, group='item')
            if len(pool) == 0:
                raise RuntimeError('pool is empty')
        else:
            # It assume that empty pool menas for all items
            pool = np.array([], dtype=np.int32)
        topks, scores = super()._most_similar(indexes, self.algo.L0, topk, pool)
        if repr:
            topks = [[self.algo._idmanager.itemids[t] for t in tt if t != -1] for tt in topks]
        return topks, scores

    def topk_recommendation(self, keys, topk=10, pool=None):
        raise NotImplemented


# TODO: Re-think about CFR internal data structure.
class ParCFR(Parallel):
    pass
