'''Spectral Modelling'''

from __future__ import print_function, division
import numpy as np


class BaseSpectrum(object):
    r"""Base class for spectral models of the form"""
    
    def __init__(self):
        pass

    def __call__(self, E, **kwargs):
        pass

    def __str__(self):
        r"""String representation"""
        return "Base spectrum"

    def copy(self):
        r"""Return copy of this class"""
        c = type(self).__new__(type(self))
        c.__dict__.update(self.__dict__)
        return c
      
      
class PowerLaw(BaseSpectrum):
    r"""Powerlaw spectrum"""
    
    def __init__(self, E0, A, gamma, Ecut=None):
        self.E0 = E0
        self.A = A
        self.gamma=gamma
        self.Ecut=Ecut
    
    def __call__(self, E, **kwargs):
        r"""Evaluate spectrum at energy E according to

                 dN/dE = A (E / E0)^-gamma

        where A has units of events / (GeV cm^2 s). We treat
        the 'events' in the numerator as implicit and say the
        units are [GeV^-1 cm^-2 s^-1]. Specifying Ecut provides
        an optional spectral cutoff according to

                 dN/dE = A (E / E0)^-gamma * exp( -E/Ecut )

        Parameters
        ----------
        E : float
            Evaluation energy [GeV]
        \*\*kwargs
            Additional arguments for over-riding member data

        Returns
        -------
        flux : float
            Flux at energy E in [GeV^-1cm^-2s^-1]
        """
        A = kwargs.pop("A", self.A)
        E0 = kwargs.pop("E0", self.E0)
        Ecut = kwargs.pop("Ecut", self.Ecut)
        gamma = kwargs.pop("gamma", self.gamma)

        flux = A * (E / E0)**(-gamma)

        # apply optional exponential cutoff
        if Ecut is not None:
            flux *= np.exp(-E / self.Ecut)

        return flux
        
    def __str__(self):
        r"""String representation"""
        return "PowerLaw"
    
    
class CustomSpectrum(BaseSpectrum):
    r'''Custom spectrum using astromodel'''
    def __init__(self,likelihood_model_instance):
        self.model = likelihood_model_instance
        
    def __call__(self, E, **kwargs):
        r"""Evaluate spectrum at E """
        return self.model.get_point_source_fluxes(id=0,energies=E)
        
    def __str__(self):
        r"""String representation of class"""
        return "CustomSpectrum"