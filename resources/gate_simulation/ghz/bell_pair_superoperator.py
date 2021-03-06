import numpy as np
import qutip as qt
import sympy as sp
from . import gate_simulation_functions

class Superoperator():
    '''
    Class designed for superoperator simulations. 
    It is valid no matter the simulation setting as long as the lindblad operators are not time dependant.
    '''
        
    def __init__(self, SimulationClass):
        self.setup = SimulationClass.setup
        self.parameters = SimulationClass.parameters
        self.realistic_parameters = SimulationClass.realistic_parameters
        self.variables = SimulationClass.variables

        self.obtain_lindblads()
        self.project_on_gs_dec_subspace()
        self.basic_substitution(gamma_g_is_zero =False)


    def obtain_lindblads(self):
        '''
        Retrieve lindblad operators from the system class.
        '''
        self.lind_op_number = len(self.setup.lindblad_list)
        self.eff_lind = []
        self.eff_lind_master_eq = []
        self.eff_lind_coeff = []
        for lind_op in range(self.lind_op_number ):
            self.eff_lind_coeff.append(self.setup.L_coeffs[lind_op])
            L_meq =  self.setup.eff_lindblad_list[lind_op]
            
            self.eff_lind_master_eq.append(L_meq)

    def project_on_gs_dec_subspace(self):
        '''
        This function eliminates the first excited state to facilitate the simulations.
        New indexing is calculated before the projection. 
        '''
        
        GsE1DecPos = np.arange(self.setup.gs_e1_dec_dim)

        GsDecPos = np.delete(GsE1DecPos ,self.setup.pos_e1)

        self.GsPosInGsDec = []
        for p in self.setup.pos_gs:
            where = np.where(GsDecPos == p)[0][0]
            self.GsPosInGsDec.append(where)
        self.GsPosInGsDec = np.array(self.GsPosInGsDec)
                       
        self.DecPosInGsDec = []
        for p in self.setup.pos_dec:
            where = np.where(GsDecPos == p)[0][0]
            self.DecPosInGsDec.append(where)
        self.DecPosInGsDec = np.array(self.DecPosInGsDec)                    
        
        #project the hamiltonian and the lindblads
        self.eff_hamiltonian = sp.Matrix( self.setup.eff_hamiltonian[ [k for k in GsDecPos] ,  [k for k in GsDecPos]] )

        for lind_op in range(self.lind_op_number ):  
            self.eff_lind_master_eq[lind_op] = sp.Matrix(  self.eff_lind_master_eq[lind_op][ [k for k in GsDecPos] ,  [k for k in GsDecPos]] )

    
    def basic_substitution(self,gamma_g_is_zero):
        '''
        Substitutes into the Hamiltonian and the Lindblad operators the self.parameters dictionary values.
        '''
        params_dict = self.realistic_parameters
        self.gamma_g_is_zero = gamma_g_is_zero
        
        if self.gamma_g_is_zero:
            params_dict = self.parameters
        else:
            params_dict = self.realistic_parameters

        self.eff_hamiltonian_C = gate_simulation_functions.posify_array( self.eff_hamiltonian.subs(params_dict))#self.eff_hamiltonian.subs(params_dict) #

        self.eff_lind_master_eq_C = []
        for lind_op in range(self.lind_op_number):
            L_op = gate_simulation_functions.posify_array(self.eff_lind_master_eq[lind_op].subs(params_dict))#self.eff_lind_master_eq[lind_op].subs(params_dict)#gate_simulation_functions.posify_array(self.eff_lind_master_eq[lind_op].subs(params_dict))
            self.eff_lind_master_eq_C.append(L_op)


    def simulate(self, parameter_dict ,analytical_output , gamma_g_is_zero):
        '''
        Run simulation for a specified set of values.

        parameter_dict

        realistic : boolean
        '''
        
        if analytical_output == True:
            tuning_dict = parameter_dict['tuning']
            tuning_dict[sp.Symbol('Delta_e0')] =  tuning_dict[sp.Symbol('Delta_e')] - parameter_dict["hardware"][sp.Symbol('Delta_max')] 
            tuning_dict[sp.Symbol('r1_p')] =tuning_dict[sp.Symbol('r0_p')]
            tuning_dict[sp.Symbol('r1_i')] =tuning_dict[sp.Symbol('r0_i')]
            tuning_dict[sp.Symbol('c')] = parameter_dict['hardware'][sp.Symbol('c')]
        else:
            tuning_dict = parameter_dict
            
        # Change the numerical substitution if needed for gamma_g=0
        if gamma_g_is_zero != self.gamma_g_is_zero:
            self.basic_substitution(gamma_g_is_zero)
        
        # Default bad performance
        performance = {'fidelity': 0 , 'p_success': 0 , 'gate_time': 10**24,'concurrence': 0}
        gs_pos = self.GsPosInGsDec   

        # Calculate superoperator
        eff_hamiltonian_num = self.eff_hamiltonian_C.subs(tuning_dict)
        eff_hamiltonian_num = eff_hamiltonian_num.expand()
        eff_hamiltonian_num = sp.re(eff_hamiltonian_num)
        eff_hamiltonian_num = np.array(eff_hamiltonian_num).astype(np.float64)

        H_obj = qt.Qobj(eff_hamiltonian_num)

        L_obj_list = []
        for lind_op in range(len(self.eff_lind_master_eq_C)):
            L_nparray = self.eff_lind_master_eq_C[lind_op].subs(tuning_dict).expand()
            L_nparray =  np.array(L_nparray).astype(complex)
            L_obj_list.append(qt.Qobj(L_nparray))
            
        self.L_obj_list = L_obj_list
        
        L = qt.liouvillian_ref(H_obj,L_obj_list)

        # Initialisation
            # On gs subspace
        plus_plus_state = np.ones(4)/2
        init_state_gs = qt.Qobj(plus_plus_state)
        for i in range(2):
            rot = tuning_dict[sp.Symbol(f'r{i}_i')]           
            to_be_tensored = [qt.identity(2) , qt.identity(2)]
            to_be_tensored[i] = qt.qip.operations.ry(rot)
            R = qt.Qobj(qt.tensor( to_be_tensored ).full())
            init_state_gs = R*init_state_gs
            
            # Project on gs-dec subspace
        init_state_full = np.zeros(self.setup.gs_dim +self.setup.dec_dim,dtype=complex)
        for i,pos in enumerate(gs_pos):
            init_state_full[pos] = init_state_gs[i]
        psi0 = qt.Qobj(init_state_full)

        
        # Turn into vectorized density matrix
        init_dm = qt.ket2dm(psi0)
        init_vec_dm = qt.operator_to_vector(init_dm)


        # Calculate gate time
        
        H = [eff_hamiltonian_num[gs_pos[0],gs_pos[0]], eff_hamiltonian_num[gs_pos[1],gs_pos[1]]\
            ,eff_hamiltonian_num[gs_pos[2],gs_pos[2]], eff_hamiltonian_num[gs_pos[3],gs_pos[3]]]
        
        gate_time =  np.abs( np.pi  /(H[3]+H[0]-H[1]-H[2]) ) * tuning_dict[sp.Symbol('tgr')] 

        
        if np.isposinf(gate_time) or np.isneginf(gate_time):
            return  performance
        

        # Simulate
        Lt = (L*gate_time).expm()
        dm_f_vec = Lt*init_vec_dm
        
        dm_f = qt.vector_to_operator(dm_f_vec)

        
        # Eliminate decayed states and extract probability of success
        dec_pos = self.DecPosInGsDec
        
        Psuccess = 1
        for pos in dec_pos:
            Psuccess -= dm_f[pos,pos]
        p_success = np.real(Psuccess)

        # Final density matrix projected on ground state subspace
        dm_f_gs =   1/ Psuccess * dm_f.eliminate_states(dec_pos) 
        

        # Post process rotations
        # Target state. 
        # The post gate rotations are "given" to the target state.
        
        
        standard_rot = gate_time * (H[0]-H[1])
        for i in range(2):
            to_be_tensored = [qt.identity(2),qt.identity(2)]
            rot =  ( tuning_dict[sp.Symbol(f'r{i}_p')]  + standard_rot   )  
            to_be_tensored[i] = qt.qip.operations.rz(rot)
            R = qt.Qobj(qt.tensor( to_be_tensored ).full())

            dm_f_gs = R*dm_f_gs*R.dag()

        hadamard_1 = qt.Qobj(qt.tensor([qt.identity(2) , qt.qip.operations.hadamard_transform(1)]).full())

        dm_f_gs = hadamard_1*dm_f_gs*hadamard_1.dag()

        # Obtain fidelity
        ghz_state = qt.Qobj(np.array([1,0,0,1])/np.sqrt(2))  
        fidelity = qt.fidelity(dm_f_gs,ghz_state)

        
        # Reset the dimensions as 2 qubit tensor so that concurrence function can be called
        dm_f_gs.dims =  [[2, 2], [2, 2]] 
        concurrence = qt.concurrence(dm_f_gs)

        performance = {'fidelity': fidelity , 'p_success': p_success , 'gate_time': gate_time,'concurrence': concurrence,
                        'density_matrix': dm_f_gs.data.toarray()}

        return performance


