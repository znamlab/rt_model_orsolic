#!/usr/bin/env python3

from pathlib import Path

import defopt
import numpy as np
import pandas as pd
import gpflow.kernels

from gp_model import build_model, prepare_X, predict_logpmf, extract_filters

def make_predictions(model, model_opts, model_params, dset, nsamples=200):
    # generate expected logit-hazard rate
    Xs = prepare_X(dset, model.n_lags, model.max_nt)
    dset['logit_hazard'] = [model.predict_f(X)[0] for X in Xs]

    # add filtered signal if projected kernel
    if 'proj' in model_opts['kernels_input']:
        W = next(v for (k, v) in model_params.items() if k.endswith('/W'))
        Xs_proj = [X[:, :-3].dot(W) for X in Xs]
        dset['projected_stim'] = Xs_proj

    # decompose prediction if additive kernel
    if isinstance(model.kern, gpflow.kernels.Sum):
        logit_hazard = zip(*[model.predict_f_partial(X) for X in Xs])
        for hazard, k_input in zip(logit_hazard, model_opts['kernels_input']):
            dset['logit_hazard_{}'.format(k_input)] = hazard

    # sample predictive distribution
    if nsamples is not None:
        dset['log_pmf'] = predict_logpmf(model, dset, nsamples)

    return dset

def main(result_dir, pred_filename, *, nsamples=None, zero_filter=None):
    """Generate predictions from a fitted GP model for experimental data

    :param str result_dir: directory of the fitted Gaussian process
    :param str pred_filename: output Pandas dataset file (.pickle format)
    :param int nsamples: number of samples to estimate posterior lick
                         probability, not computed by default
    :param int zero_filter: make predictions with one of the filters set to 0
    """

    # fix seed for reproducibility
    seed = 12345
    np.random.seed(seed)

    # load dataset and model
    result_path = Path(result_dir)
    dset = pd.read_pickle(result_path / 'dataset.pickle')

    model_opts = np.load(result_path / 'model_options.npz')
    model = build_model(dset[dset.train], fast_init=True, **model_opts)
    model_params = dict(np.load(result_path / 'model_params_best.npz'))

    if zero_filter is not None:
        _, filters_idx, _ = extract_filters(model_params)
        model_params['PartialSVGP/kern/kernels/0/W'][:, filters_idx[zero_filter]] = 0

    model.assign(model_params)

    dset = make_predictions(model, model_opts, model_params, dset, nsamples)
    # save predictions
    dset.to_pickle(pred_filename)


if __name__ == "__main__":
    defopt.run(main)
