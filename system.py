import qutip as qt
import numpy as np
import matplotlib.pyplot as plt
from scipy.sparse import csr_matrix
import sage.all as sg
import time

from components import *
from functions import *

class system:
    '''
    Class defining a system of elements.

    Initialize by giving a string containing:
    x : auxiliary atom
    o : Borregaard atom
    - : optical fiber
    
    Corresponding state-vectors and corresponding excitations will be initialized.

    ...

    Attributes
    ----------
    size : int
        Number of elements
    dim : int
        Total dimension of the system. 
    elements: list 
        List of all element objects.
    dim_list: list
        List with every dimension_list  of every element.
    flattened_dim_list : list
        List of all dimensions
    
    
    Methods
    -------
    hamiltonian
    '''
 
    def __init__(self, system_string):
        self.size = len(system_string)
        self.elements = []
        self.dim_list =[]
        self.dim = 1  
        dim_pos = 0
        for ( pos , el_type ) in enumerate(system_string):
            self.elements.append( element( pos, el_type, dim_pos ) )
            dim_pos +=  self.elements[-1].size
            self.dim *=  self.elements[-1].dim
            self.dim_list.append(self.elements[-1].dim_list)

        self.update_subelements()
        print('Constructing states and excitations...')
        self.construct_states_and_excitations()
        print('Constructing ground and first-excited statespace...')
        self.construct_gs_e1_subspace()
        self.obtain_energy_info()    
        print('Constructing gs_hamiltonian ...')  
        self.construct_gs_hamiltonian()
        print('Constructing e1_hamiltonian ...') 
        self.construct_e1_hamiltonian()
        print('Constructing interactions V_plus and V_minus ...')
        self.construct_V()
        print(f'\nSystem  {system_string}  initialized!')


    def update_subelements(self):
        '''
        Communicate the dimension_list to all (sub)elements
        '''
        flatten = lambda t: [item for sublist in t for item in sublist] #expression that flattens list
        flattened_list = flatten(self.dim_list)
        self.flattened_dim_list = flattened_list 
        for elem in self.elements:
            elem.system_dim_list = flattened_list
            for sub_elem in elem.sub_elements:
                sub_elem.system_dim_list = flattened_list



    def construct_states_and_excitations(self):
        self.excitations = np.empty(self.dim, dtype= f'U{len(self.flattened_dim_list)}')
        self.states = np.empty(self.dim, dtype= f'U{len(self.flattened_dim_list) * 4 }')

        #This code does "tensor product" for characters
        times_to_be_tensored = 1
        sub_elem_dim_prod = 1
        for elem in self.elements:
            for sub_elem in elem.sub_elements:
                sub_elem_dim_prod *= sub_elem.dim
                for  t in range( times_to_be_tensored):
                    subblock_start = int(t/times_to_be_tensored*self.dim)
                    for i in range(sub_elem.dim):
                        slice_start = int( (i*self.dim / sub_elem_dim_prod ) + subblock_start  )
                        slice_end = int(( (i+1) *self.dim/sub_elem_dim_prod ) + subblock_start )
                        for j in range(slice_start,slice_end):
                            self.excitations[j] += sub_elem.excitations[i]
                            self.states[j] += sub_elem.states[i]
                times_to_be_tensored *= sub_elem.dim         


                
    def construct_gs_e1_subspace(self):
        
        self.pos_to_del_gs_e1 = []
        for (i , excitation ) in enumerate(self.excitations) :
            gs_del_flag = False
            e1_del_flag = False
            e_num = 0
            for char in excitation:
                if char not in ('g' , 'q') : 
                    gs_del_flag = True
                if char == 'e' or char == 'd' : 
                    e_num += 1 
                if char == 'q' : # we cant access starting state
                    e1_del_flag = True
            if e_num != 1 : e1_del_flag = True
            
            if e1_del_flag and gs_del_flag:
                self.pos_to_del_gs_e1.append(i)
        
        #self.pos_gs_e1 = [i for i in [*range(self.dim)] if i not in self.pos_to_del_gs_e1]   DELETED DUE TO IT BEING TOO SLOW
        self.gs_e1_dim = self.dim - len(self.pos_to_del_gs_e1)
        self.gs_e1_excitations = np.delete(self.excitations , self.pos_to_del_gs_e1)
        self.gs_e1_states = np.delete(self.states , self.pos_to_del_gs_e1)

        # gs_hamiltonian states and positions in gs_e1 subspace

        self.pos_to_del_gs = []
        for (i , excitation ) in enumerate(self.gs_e1_excitations) :            
            for char in excitation:
                if char not in ('g' , 'q') : 
                    self.pos_to_del_gs.append(i)
        self.pos_to_del_gs = list(dict.fromkeys(self.pos_to_del_gs)) #remove duplicates
        
        self.gs_dim = self.gs_e1_dim - len(self.pos_to_del_gs)

        self.pos_gs = [i for i in [*range(self.gs_dim)] if i not in self.pos_to_del_gs]  #all positions that contain gs in gs_e1

                
        self.gs_states = np.delete(self.gs_e1_states, self.pos_to_del_gs )
        self.gs_excitations = np.delete(self.gs_e1_excitations, self.pos_to_del_gs )


        # e1_hamiltonian states and positions in gs_e1 subspace
        
        self.pos_to_del_e1 = []
        for (i , excitation ) in enumerate(self.gs_e1_excitations) : 
            e_num = 0
            for char in excitation:
                if char == 'e' or char == 'd' : 
                    e_num += 1 
                if char == 'q' : # we cant access starting state
                    self.pos_to_del_e1.append(i) 
                    e_num += 2
            if e_num != 1 : self.pos_to_del_e1.append(i) 
        self.pos_to_del_e1 = list(dict.fromkeys(self.pos_to_del_e1)) #remove duplicates
        
        self.e1_dim = self.gs_e1_dim - len(self.pos_to_del_e1)  

        self.pos_e1 = [i for i in [*range(self.e1_dim)] if i not in self.pos_to_del_e1]  #all positions that contain gs in gs_e1

        self.e1_states = np.delete(self.gs_e1_states, self.pos_to_del_e1 )
        self.e1_excitations = np.delete(self.gs_e1_excitations, self.pos_to_del_e1 )



    def obtain_energy_info(self):
        self.H_list = []
        self.H_coeffs = []
        self.gs_e1_int =[]
        for elem in self.elements:
            for sub_elem in elem.sub_elements:
                h = sub_elem.hamiltonian()             
                for (i,h_el) in enumerate(h):
                    self.H_list.append(h[i])
                    self.H_coeffs.append(sub_elem.H_coeffs[i])
                    self.gs_e1_int.append(sub_elem.gs_e1_interaction[i])



    def construct_gs_hamiltonian(self):
        '''
        Constructs ground state Hamiltonian in gs_e1 subspace, corresponding state-vectors and corresponding excitation.

        Note that the gs_hamiltonian will be a numpy array and not a qt objeect.
        '''
        self.gs_hamiltonian = np.zeros((self.gs_e1_dim,self.gs_e1_dim) , dtype = 'complex128')

        self.gs_hamiltonian = sg.matrix(self.gs_hamiltonian )

        for (coeff , h) in zip(self.H_coeffs,self.H_list):
            h_reduced = delete_from_csr( h.data, row_indices=self.pos_to_del_gs_e1, col_indices=self.pos_to_del_gs_e1).toarray() 
            h_reduced[self.pos_e1, :]  = 0
            h_reduced[: , self.pos_e1] = 0
            self.gs_hamiltonian = self.gs_hamiltonian + coeff * sg.matrix(h_reduced)
        
        ones_w_0diag = np.ones((self.gs_e1_dim,self.gs_e1_dim))
        np.fill_diagonal(ones_w_0diag , 0)
        ones_w_0diag = sg.matrix(ones_w_0diag ) + sg.var('x')*sg.matrix(np.zeros((self.gs_e1_dim,self.gs_e1_dim)))

                 


        self.gs_hamiltonian =  self.gs_hamiltonian   + elementwise(sg.operator.mul, self.gs_hamiltonian , ones_w_0diag).conjugate_transpose()



    def construct_e1_hamiltonian(self):
        '''
        Constructs the first excited state Hamiltonian in gs_e1 subspace, corresponding state-vectors and corresponding excitation.

        Note that the e1_hamiltonian will be a numpy array and not a qt objeect.
        '''
        
        self.e1_hamiltonian = sg.matrix ( np.zeros((self.gs_e1_dim,self.gs_e1_dim), dtype = 'complex128') )

        for (coeff , h) in zip(self.H_coeffs,self.H_list):
            h_reduced = delete_from_csr( h.data, row_indices=self.pos_to_del_gs_e1, col_indices=self.pos_to_del_gs_e1).toarray()
            h_reduced[self.pos_gs, :]  = 0
            h_reduced[: , self.pos_gs] = 0       
            self.e1_hamiltonian += coeff * sg.matrix( h_reduced  )     

        ones_w_0diag = np.ones((self.gs_e1_dim,self.gs_e1_dim))
        np.fill_diagonal(ones_w_0diag , 0)
        ones_w_0diag = sg.matrix(ones_w_0diag ) + sg.var('x')*sg.matrix(np.zeros((self.gs_e1_dim,self.gs_e1_dim)))

        self.e1_hamiltonian = self.e1_hamiltonian   + elementwise(sg.operator.mul, self.e1_hamiltonian , ones_w_0diag).conjugate_transpose()




    def construct_V(self):
        '''
        Constructs  V+ and V- in gs_e1 subspace, corresponding state-vectors and corresponding excitation.

        Note that the e1_hamiltonian will be a numpy array and not a qt objeect.
        '''
        self.e1_gs_dim = self.gs_dim + self.e1_dim
        self.V_plus = sg.matrix( np.zeros((self.e1_gs_dim,self.e1_gs_dim) , dtype = 'complex128')  ) * sg.var('x')

        for (coeff , h , gs_e1_interaction) in zip(self.H_coeffs,self.H_list , self.gs_e1_int):
            if gs_e1_interaction:
                h_reduced = delete_from_csr( h.data, row_indices=self.pos_to_del_gs_e1, col_indices=self.pos_to_del_gs_e1).toarray()
                print()
                self.V_plus += coeff * sg.matrix(h_reduced)

        
        self.V_minus = self.V_plus.conjugate_transpose()
        




class element:
    def __init__(self,  pos , type, dim_pos ):
        self.system_dim_list =[]
        self.pos = pos
        self.type = type
        self.dim_pos = dim_pos
        self.sub_elements = []
        if  type == 'x':
            self.size = 2
            self.dim = 2 * 3
            self.dim_list = [2 , 3]
            cavity_dim_pos = dim_pos
            atom_dim_pos = cavity_dim_pos + 1
            self.sub_elements.append( cavity(cavity_dim_pos,atom_dim_pos) )
            self.sub_elements.append( qutrit(atom_dim_pos , cavity_dim_pos ) )
        elif type == 'o':            
            self.dim = 2 * 4
            self.dim_list = [2 , 4]
            self.size = 2
            cavity_dim_pos = dim_pos
            atom_dim_pos = cavity_dim_pos + 1
            self.sub_elements.append( cavity( cavity_dim_pos, atom_dim_pos) )
            self.sub_elements.append( qunyb(atom_dim_pos , cavity_dim_pos ) )
        elif type == '-':
            self.size = 1
            self.dim = 2
            self.dim_list = [2] 
            cavities_connected_pos = [dim_pos-2  , dim_pos+1]   
            self.sub_elements.append( fiber( dim_pos, cavities_connected_pos ))
        else:            
            print(f'Not valid element {type}. Give o , x and -')
            exit()

    def hamiltonian(self):
        H = zero_operator(self.system_dim_list)
        for sub_elem in self.sub_elements:
            H += sub_elem.hamiltonian()
        return H


        