# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 16:12:04 2019

@author: Zero_Zhou
"""
# -*- coding: utf-8 -*-
# implementation of https://github.com/joyeecheung/dark-channel-prior-dehazing
# index of pictures is [vertical][horizontal][depth]


"""
Usage in IPython console:
    import DCP_GF_Final
    im_path = "path(use \\ as separator)"
    im_dehaze = DCP_GF.dehaze(im_path, ...)
    cv2.imshow('image', im_dehaze[i])
    cv2.waitKey(0)
        

"""  


import cv2
import numpy as np
import guidedfilter



def get_dark_channel(I, w):
    """Get the dark channel prior in the (RGB) image data.

    Parameters
    -----------
    I:  an M * N * 3 numpy array containing data ([0, L-1]) in the image where
        M is the height, N is the width, 3 represents R/G/B channels.
    w:  window size

    Return
    -----------
    An M * N array for the dark channel prior ([0, L-1]).
    """
    M, N, _ = I.shape
    padded = np.pad(I, ((w // 2, w // 2), (w // 2, w // 2), (0, 0)), 'edge')
    darkch = np.zeros((M, N))
    for i, j in np.ndindex(darkch.shape):
        darkch[i, j] = np.min(padded[i:i + w, j:j + w, :])  # CVPR09, eq.5
    return darkch

def get_atmosphere(I, darkch, p):
    """Get the atmosphere light in the (RGB) image data.

    Parameters
    -----------
    I:      the M * N * 3 RGB image data ([0, L-1]) as numpy array
    darkch: the dark channel prior of the image as an M * N numpy array
    p:      percentage of pixels for estimating the atmosphere light

    Return
    -----------
    A 3-element array containing atmosphere light ([0, L-1]) for each channel
    """
    # reference CVPR09, 4.4
    M, N = darkch.shape
    flatI = I.reshape(M * N, 3)
    flatdark = darkch.ravel() #arranged horizontally
    searchidx = (-flatdark).argsort()[:round(M * N * p)]
#   print ('atmosphere light region:', [(i / N, i % N) for i in searchidx])

    # return the highest intensity for each channel
    return np.max(flatI.take(searchidx, axis=0), axis=0)

def get_transmission(I, A, darkch, omega, w):
    """Get the transmission esitmate in the (RGB) image data.

    Parameters
    -----------
    I:       the M * N * 3 RGB image data ([0, L-1]) as numpy array
    A:       a 3-element array containing atmosphere light
             ([0, L-1]) for each channel
    darkch:  the dark channel prior of the image as an M * N numpy array
    omega:   bias for the estimate
    w:       window size for the estimate

    Return
    -----------
    An M * N array containing the transmission rate ([0.0, 1.0])
    """
    return 1 - omega * get_dark_channel(I / A, w)  # CVPR09, eq.12

def dehaze_raw(I, tmin, Amax, w, p,
               omega, guided, r, eps):
    """Get the dark channel prior, atmosphere light, transmission rate
       and refined transmission rate for raw RGB image data.

    Parameters
    -----------
    I:      M * N * 3 data as numpy array for the hazy image
    tmin:   threshold of transmission rate
    Amax:   threshold of atmosphere light
    w:      window size of the dark channel prior
    p:      percentage of pixels for estimating the atmosphere light
    omega:  bias for the transmission estimate

    guided: whether to use the guided filter to fine the image
    r:      the radius of the guidance
    eps:    epsilon for the guided filter

    Return
    -----------
    (Idark, A, rawt, refinedt) if guided=False, then rawt == refinedt
    """
    m, n, _ = I.shape
    Idark = get_dark_channel(I, w)

    A = get_atmosphere(I, Idark, p)
    A = np.minimum(A, Amax)  # threshold A
#    print ('atmosphere', A)

    rawt = get_transmission(I, A, Idark, omega, w)
#    print ('raw transmission rate', rawt)
#    print ('between [%.4f, %.4f]' % (rawt.min(), rawt.max()))

    rawt = refinedt = np.maximum(rawt, tmin)  # threshold t
    if guided:
        normI = (I - I.min()) / (I.max() - I.min())  # normalize I
        refinedt = guidedfilter.guided_filter(normI, refinedt, r, eps)
        
#    print ('refined transmission rate',refinedt)
#    print ('between [%.4f, %.4f]' % (refinedt.min(), refinedt.max()))

    return Idark, A, rawt, refinedt

def get_radiance(I, A, t):
    """Recover the radiance from raw image data with atmosphere light
       and transmission rate estimate.

    Parameters
    ----------
    I:      M * N * 3 data as numpy array for the hazy image
    A:      a 3-element array containing atmosphere light
            ([0, L-1]) for each channel
    t:      estimate fothe transmission rate

    Return
    ----------
    M * N * 3 numpy array for the recovered radiance
    """
    tiledt = np.zeros_like(I)  # tiled to M * N * 3
    tiledt[:, :, R] = tiledt[:, :, G] = tiledt[:, :, B] = t
    return (I - A) / tiledt + A  # CVPR09, eq.16

def dehaze(im_path, tmin, Amax, w, p,
           omega, guided, r, eps):
    """Dehaze the given RGB image.

    
    ----------
    (dark, rawt, refinedt, rawrad, rerad)
    Images for dark channel prior, raw transmission estimate,
    refiend transmission estimate, recovered radiance with raw t,
    recovered radiance with refined t.
    """
    im = cv2.imread(im_path)
    I = np.asarray(im, dtype=np.float64)
    Idark, A, rawt, refinedt = dehaze_raw(I, tmin, Amax, w, p,
                                          omega, guided, r, eps)
    white = np.full_like(Idark, L - 1) # generate white picture

    def to_img(raw):
        # threshold to [0, L-1]
        return np.maximum(np.minimum(raw, L - 1), 0).astype(np.uint8)

    return [to_img(raw) for raw in (Idark, white * rawt, white * refinedt,
                                    get_radiance(I, A, rawt),
                                    get_radiance(I, A, refinedt))]


if __name__ =="__main__":

    p = 0.001  # percent of pixels
    W = 16     # window size
    omega = 0.95 # omega before transmission
    R, G, B = 0, 1, 2  # index for convenience
    L = 256  # color depth
    im_path = r'H:\Undergraduate\18-19-3\Undergraduate Thesis\Dataset\test_images_data\0001_0.8_0.1.jpg'
    im_dehaze = dehaze(im_path, tmin=0.2, Amax=220, w=W, p=p,
           omega=omega, guided=True, r=40, eps=1e-3)










































