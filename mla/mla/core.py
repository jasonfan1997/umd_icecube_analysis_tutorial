'''Core functionality'''

from __future__ import print_function, division
import os, sys, glob, numpy as np, matplotlib, scipy, healpy as hp, time
from scipy import stats, interpolate, optimize
from math import pi
import numpy.lib.recfunctions as rf
from mla.spectral import *
from mla.tools import *
import scipy.stats

def build_bkg_spline(data , bins=np.linspace(-1.0, 1.0, 501) , file_name=None): 
    ''' build the dec-background spline '''
    sin_dec = np.sin(data['dec'])
    
    hist, bins = np.histogram(sin_dec, 
                        bins=bins, 
                        weights=np.ones_like(data['dec'])/len(data['dec']))
                        
    bg_p_dec = interpolate.UnivariateSpline(bins[:-1]+np.diff(bins)/2., 
                                        hist,
                                        bbox=[-1.0, 1.0],
                                        s=1.5e-5,
                                        ext=1)
    
    return bg_p_dec
    
def scale_and_weight_trueDec(sim , source_dec , sampling_width = np.radians(1)):
    ''' scaling the Monte carlo using trueDec
    This is for calculating expected signal given spectrum'''
    sindec_dist = np.abs(source_dec-sim['trueDec'])
    
    close = sindec_dist < sampling_width
    
    reduced_sim = sim[close].copy()
    
    omega = 2*np.pi * (np.min([np.sin(source_dec+sampling_width), 1]) -\
                       np.max([np.sin(source_dec-sampling_width), -1]))             
    reduced_sim['ow'] /= omega
    
    return reduced_sim

def scale_and_weight_dec(sim , source_dec , sampling_width = np.radians(1)):
    ''' scaling the Monte carlo using dec
    This is for calculating energy S/B
    Notice that we doesn't change ow here it is unnessary'''
    sindec_dist = np.abs(source_dec-sim['dec'])
    
    close = sindec_dist < sampling_width
    
    reduced_sim = sim[close].copy()
    
    return reduced_sim
    
def build_bkg_2dhistogram(data , bins=[np.linspace(-1,1,100),np.linspace(1,8,100)]):
    ''' build the background 2d histogram for energy S/B'''
    bg_w=np.ones(len(data),dtype=float)
    
    bg_w/=np.sum(bg_w)
    
    bg_h,xedges,yedges=np.histogram2d(np.sin(data['dec']),data['logE'],bins=bins
                                      ,weights=bg_w)
    return bg_h,bins
    
    
class LLH_point_source(object):
    '''The class for point source'''
    def __init__(self , ra , dec , data , sim , livetime , spectrum , bkg_bins=np.linspace(-1.0, 1.0, 501) , sampling_width = np.radians(1) , bkg_2dbins=[np.linspace(-1,1,300),np.linspace(1,8,100)]):
        ''' Constructor of the class'''
        self.ra = ra
        self.dec = dec
        self.bg_h,self.energybins = build_bkg_2dhistogram(data , bins = bkg_2dbins)
        self.bkg_spline = build_bkg_spline(data , bins = bkg_bins)
        self.sim = scale_and_weight_trueDec(sim , dec , sampling_width = sampling_width)# Notice that this is for expected signal calculation
        self.sim_dec = scale_and_weight_dec(sim , dec , sampling_width = sampling_width)# This is for Energy S/B ratio calculation
        self.fullsim = sim #The full simulation set,this is for the overall normalization of the Energy S/B ratio
        self.N = len(data) #The len of the data
        self.spectrum = spectrum
        self.data = data
        self.livetime = livetime
        self.update_spatial() #Calculating the spatial llh and drop all data with zero signal spatial llh
        self.sample_size = 0
        return
       
    def update_spatial(self):
        '''Calculating the spatial llh and drop data with zero spatial llh'''
        signal = self.signal_pdf()
        mask = signal!=0
        self.data = self.data[mask]
        self.spatial = signal[mask]/self.background_pdf()  
        return
        
    def updata_spectrum(self,spectrum):
        ''' update the spectrum'''
        self.spectrum = spectrum
        return
        
        
    def cut_data(self , data , time_range ):
        '''Select data within some time range'''
        mask = (data['time']>time_range[0]) & (data['time']<=time_range[1])
        self.data = data[mask]
        self.N = len(data)
        self.update_spatial()
        return
        
    def update_data(self , data ,livetime):
        '''Change the data'''
        self.data = data
        self.livetime = livetime
        self.N = len(data)
        self.update_spatial()
        return
        
    def signal_pdf(self):
    
        distance = angular_distance(self.data['ra'], 
                                    self.data['dec'], 
                                    self.ra, 
                                    self.dec)
        sigma = self.data['angErr']
        return (1.0)/(2*np.pi*sigma**2)**0.5 * np.exp(-(distance)**2/(2*sigma**2))

    def background_pdf(self):
    
        background_likelihood = (1/(2*np.pi))*self.bkg_spline(np.sin(self.data['dec']))
        return background_likelihood
    
    def energy_weight(self):
        '''enegy weight calculation. This is slow if you choose a large sample width'''
        i=np.searchsorted(self.energybins[0],np.sin(self.data['dec']))-1
        j=np.searchsorted(self.energybins[1],self.data['logE'])-1
        sig_w=self.sim_dec['ow'] * self.spectrum(self.sim_dec['trueE'])
        sig_w/=np.sum(self.fullsim['ow'] * self.spectrum(self.fullsim['trueE']))
        sig_h,xedges,yedges=np.histogram2d(np.sin(self.sim_dec['dec']),self.sim_dec['logE'],bins=self.energybins,weights=sig_w)
        ratio=sig_h/self.bg_h
        for k in range(ratio.shape[0]):
            values=ratio[k]
            good=np.isfinite(values)&(values>0)
            x,y=self.energybins[1][:-1][good],values[good]
            if len(x) > 1:
                spline=scipy.interpolate.UnivariateSpline(x,y,k=1,s=0,ext=3)
                ratio[k]=spline(self.energybins[1][:-1])
            elif len(x)==1:
                ratio[k]=y
            else:
                ratio[k]=0
        return ratio[i,j]
        
    def eval_llh(self):
        '''Calculating the llh using the spectrum'''
        ns = (self.sim['ow'] * self.spectrum(self.sim['trueE']) * self.livetime * 24 * 3600).sum()     
        energy = self.energy_weight()
        ts =( ns/self.N * (energy*self.spatial - 1))+1
        return ns,2*np.sum(np.log(ts))
    
    def eval_llh_ns(self,ns):     
        '''Calculating the llh with user-input ns'''
        energy = self.energy_weight()
        ts =( ns/self.N * (energy*self.spatial - 1))+1
        return ns,2*np.sum(np.log(ts))
    
    def add_injection(self,sample):
        '''Add injected sample'''
        self.sample_size = len(sample)+self.sample_size
        sample = rf.drop_fields(sample, [n for n in sample.dtype.names \
                         if not n in self.data.dtype.names])
        self.data = np.concatenate((self.data,sample))
        self.N = len(self.data)
        self.update_spatial()
        return
    
    def remove_injection(self):
        '''remove injected sample'''
        self.data = self.data[:len(self.data)-self.sample_size]
        self.N = len(self.data)
        self.update_spatial()
        return
        
    def modify_injection(self,sample):
        '''modify injected sample'''
        self.remove_injection()
        self.add_injection(sample)
        return 
        