from math import exp, ceil
import os
import re
from random import choice
from AmberMaps import *
from wrapper import *
from Class_Structure import *
from Class_line import *
from Class_Conf import Config, Layer
from helper import line_feed, mkdir
try:
    from pdb2pqr.main import main_driver as run_pdb2pqr
    from pdb2pqr.main import build_main_parser as build_pdb2pqr_parser
except ImportError:
    raise ImportError('PDB2PQR not installed.')

try:
    import propka.lib
except ImportError:
    raise ImportError('PropKa not installed.')
try:
    import openbabel
    import openbabel.pybel as pybel
except ImportError:
    raise ImportError('OpenBabel not installed.')



__doc__='''
This module handles file I/O and external programs.
-------------------------------------------------------------------------------------
Class PDB
-------------------------------------------------------------------------------------
__init__(self, PDB_input, wk_dir = '', name = '', input_type='path')
-------------------------------------------------------------------------------------
Information collecting methods:
-------------------------------------------------------------------------------------
get_stru(self, ligand_list=None)
get_seq(self)
get_if_ligand = get_seq # alias
get_if_art_resi = get_seq # alias
get_missing(self, seq)
-------------------------------------------------------------------------------------
PDB operating methods: (changes the self.path to indicated new pdb)
-------------------------------------------------------------------------------------
PDB2PDBwLeap(self, Flag):
PDBMin(self,cycle):
rm_wat(self): remove water and ion for current pdb. (For potential docking)
loopmodel_refine(self): Use different method to model the missing sequence

-------------------------------------------------------------------------------------
Mutation Tools:
-------------------------------------------------------------------------------------
Add_MutaFlag(self,Flag): User assigned Flag or Random Flag using "random"
PDB_check(self):

-------------------------------------------------------------------------------------
Input file generating methods:
-------------------------------------------------------------------------------------
PDB2FF(self):
PDBMD(self):
-------------------------------------------------------------------------------------
>>>>>>> Develop Note <<<<<<<<<
For every potential first use of self.file_str or self.path or self.stru
Will do nothing if the correct var is already exist.
 - use _get_file_str
 - use _get_file_path
 - use get_stru 
'''

class PDB():
    def __init__(self, PDB_input, wk_dir = '', name = '', input_type='path'):
        '''
        initiate PDB object
        -------------------
        PDB_input
        wk_dir      : working directory (default: current dir ) **all file in the workflow are constructed base on this.**
        name        : self assigned filename (default: from path or UNKNOW if no path)
        input_type  : path (default) / file_str / file
        -------------------
        '''
        # Nessessary initilize for empty judging
        self.stru = None
        self.path = None
        self.prmtop_path = None
        self.MutaFlags = []
        # default MD conf.
        self._init_MD_conf()
        # default ONIOM layer setting
        self.layer_preset = Config.Gaussian.layer_preset
        self.layer_atoms = Config.Gaussian.layer_atoms

        if wk_dir == '':
            #current dir by default
            self.dir = '.'
        else:
            if wk_dir[-1] == '/':
                self.dir = wk_dir[:-1]
            else:
                self.dir = wk_dir

        if input_type == 'path':
            self.path = PDB_input
            self._update_name()
        if input_type == 'file_str':
            self.file_str = PDB_input
            if name == '':
                # default name
                name = 'UNKNOW'
            self.name = name
            self.path_name = self.dir+'/'+self.name
        if input_type == 'file':
            self.file_str = PDB_input.read()
            if name == '':
                # default name
                name = 'UNKNOW'
            self.name = name
            self.path_name = self.dir+'/'+self.name
        if input_type not in ['path', 'file_str', 'file']:
            raise Exception('PDB.__init__: only take path or file_str or file.')

        # make cache
        self.cache_path = self.dir+'/cache'
        mkdir(self.cache_path)
        

    def _update_name(self):
        '''
        update name
        '''
        suffix_len = len(self.path.split('.')[-1]) + 1
        self.name=self.path.split(os.sep)[-1][:-suffix_len]
        self.path_name = self.dir+'/'+self.name
        

    def get_stru(self, ligand_list=None, renew = 0):
        '''
        Convert current PDB file (self.path) to a Struture object (self.stru).
        ------
        input_name  : a name tag for the object (self.name by default)
        ligand_list : a list of user assigned ligand residue names.
        renew       : 1: force generate a new stru_obj
        '''
        # indicated by self.name
        input_name = self.name
        # if get new stru
        get_flag = 0
        if self.stru is not None:
            if self.stru.name != self.name:
                get_flag = 1
                # warn if possible wrong self.stru
                if Config.debug > 1:
                    print('PDB.get_stru: WARNING: self.stru has a different name')
                    print('     -self.name: '+self.name)
                    print('     -self.stru.name: '+self.stru.name)
                    print('Getting new stru')
        else:
            get_flag = 1

        if get_flag or renew:
            if self.path is not None:
                self.stru = Structure.fromPDB(self.path, input_name=input_name, ligand_list=ligand_list)
            else:
                self.stru = Structure.fromPDB(self.file_str, input_type='file_str', input_name=input_name, ligand_list=ligand_list)


    def _get_file_str(self):
        '''
        read file_str from path is not pre-exist.
        -------------
        recommend before every potential first use of self.file_str
        '''
        if self.path is None:
            return self.file_str
        else:
            return open(self.path).read()


    def _get_file_path(self):
        '''
        save a file and get path if self.path is None
        -------------
        recommend before every potential first use of self.path
        '''
        if self.path is None:
            self.path = self.path_name+'.pdb'
            with open(self.path,'w') as of:
                of.write(self.file_str)
        return self.path


    def _init_MD_conf(self):
        '''
        initialize default MD configuration. Replaced by manual setting if assigned later.
        '''
        self.conf_min = Config.Amber.conf_min
        self.conf_heat = Config.Amber.conf_heat
        self.conf_equi = Config.Amber.conf_equi
        self.conf_prod = Config.Amber.conf_prod


    def set_oniom_layer(self, atom_list=[], preset=0):
        '''
        set oniom layer with san check
        layer_atoms are in higher pirority
        '''
        if len(atom_list) != 0:
            if all(type(x) is str for x in atom_list):
                self.layer_atoms = atom_list
            else:
                raise Exception('set_oniom_layer: atom_list require a list of str. e.g.: [\'1-9\',\'11,13-15\']')
        else:
            if preset == 0:
                raise Exception('set_oniom_layer: please assign one of the argument: atom_list (a list of layer_atoms) or preset (other than 0)')
            else:
                self.layer_preset = preset


    '''
    =========
    Sequence TODO: reform(已部分迁移至Chain类，剩人工残基的部分和整个stru的判断)
    =========
    '''

    def get_seq(self, Oneletter=0):
        '''
        get_seq(self, Oneletter=0)
        Support most PDB types
        ----------------------------
        Oneletter
        = 0 // use 3-letter format to represet each residue
        = 1 // use 1-letter format to represet each residue
        ----------------------------
        Get sequence for current PDB (self.path) // A general function to obtain the missing residue
        + Use "NAN"/"-" as a filler to store missing residues (detect internal missing)
        + Check if contain non-standard residue with the Resi_map --> self.if_art_resi
        + Check if contain ligand with the Resi_map and TIP3P_map --> self.if_ligand
        - (WARNING) Require the ligand in seperate chains
        - Re-assign the chain_index base on the order in the file
        - Do not include the original residue index
        - Do not include any HETATM (ligand/solvent)
        ----------------------------
        save the info to self.sequence/self.sequence_one and return it
        ----------------------------
        self.sequence:
        Format: {'Chain_index':['res','res',...]
                 'Chain_index':['res','res',...]
                 ...
                }

        self.raw_sequence:
            Internal used, containing HETATM

        self.sequence_one: (when Oneletter=1)
        Format: {'Chain_index':'seq'
                 'Chain_index':'seq'
                 ...
                }

        !!NOTE!! the self.sequence needs to be updated after mutation
        '''

        PDB_str = self._get_file_str()
        self.raw_sequence = {}
        self.sequence = {}
        self.sequence_one = {}

        Chain_str = PDB_str.split(line_feed+'TER') # Note LF is required
        
        for chain,i in enumerate(Chain_str):

            Chain_index = chr(65+chain) # Covert to ABC using ACSII mapping
            Chain_sequence=[]
            
            # Get the Chain_sequence
            lines=i.split(line_feed)

            for line in lines:

                pdb_l = PDB_line(line)

                if pdb_l.line_type == 'ATOM' or pdb_l.line_type == 'HETATM':
                    
                    # Deal with the first residue
                    if len(Chain_sequence) == 0:
                        Chain_sequence.append(pdb_l.resi_name)
                        last_resi_index = pdb_l.resi_id
                        continue

                    # find next new residue
                    if pdb_l.resi_id != last_resi_index:

                        # Deal with missing residue, fill with "NAN"
                        missing_length = pdb_l.resi_id - last_resi_index - 1 
                        if missing_length > 0:
                            Chain_sequence = Chain_sequence + ['NAN',] * missing_length 
                        
                        # Store the new resi
                        Chain_sequence.append(pdb_l.resi_name)

                    # Update for next loop                
                    last_resi_index = pdb_l.resi_id
            
            self.raw_sequence[Chain_index] = Chain_sequence
            
        self._strip_raw_seq() # strip the raw_sequence and save to sequence
        
        self.get_if_complete()

        if Oneletter == 1:
            self._get_Oneletter()
            return self.sequence_one
        else:
            return self.sequence

    get_if_ligand = get_seq # alias
    get_if_art_resi = get_seq

    def _strip_raw_seq(self):
        '''
        (Used internally) strip the raw_sequence.
        - Delete ligand and solvent
        - Delete chains without residue

        save changes to self.sequence

        Judge if containing any ligand or artificial residue

        save to self.if_ligand and self.if_art_resi
        '''
        new_index=0

        #if the value is not changed to 1 then it's 0
        self.if_art_resi = 0
        self.if_ligand = 0

        if len(self.raw_sequence) == 0:
            print("The self.raw_sequence should be obtained first")
            raise IndexError

        for chain in self.raw_sequence:
            
            chain_seq=[]
            if_realchain = 0

            # Judge if real chain
            for name in self.raw_sequence[chain]:
                clean_name = name.strip(' ')
                if clean_name in Resi_map2.keys():
                    if_realchain = 1
            
            if if_realchain:
                for name in self.raw_sequence[chain]:
                    clean_name = name.strip(' ')                               
                    chain_seq.append(clean_name)

                    # An artificial residue will be a residue in a realchain but not included in force field map
                    if clean_name not in Resi_map2 and clean_name != 'NAN':
                        self.if_art_resi = 1                        
                        ## PLACE HOLDER for further operation on artificial residue ##

            else:
                # Judge if containing any ligand
                for name in self.raw_sequence[chain]:
                    clean_name = name.strip(' ') 
                    if clean_name not in TIP3P_map and clean_name != 'NAN':
                        self.if_ligand = 1
                        ## PLACE HOLDER for further operation on artificial residue ##
            
            # only add realchain to the self.sequence
            if len(chain_seq) != 0:
                chain_Index=chr(new_index+65)
                self.sequence[chain_Index]=chain_seq
                new_index=new_index+1


    def _get_Oneletter(self):
        '''
        (Used internally) convert sequences in self.sequence to oneletter-based str
        - The 'NAN' is convert to '-'
        - Present unnature residue as full 3-letter name

        save to self.sequence_one
        '''
        if len(self.sequence) == 0:
            print("The self.sequence should be obtained first")
            raise IndexError

        for chain in self.sequence:
            chain_Seq=''
            for name in self.sequence[chain]:
                c_name=name.strip(' ')
                if c_name == 'NAN':
                    chain_Seq=chain_Seq+'-'
                else:
                    if c_name in Resi_map2:
                        chain_Seq=chain_Seq+Resi_map2[c_name]
                    else:
                        chain_Seq=chain_Seq+' '+c_name+' '
                
            self.sequence_one[chain]=chain_Seq


    def get_if_complete(self):
        '''
        Judge if the self.sequence (from the get_seq) has internal missing parts
        Save the result to:
            self.if_complete ------- for intire PDB
            self.if_complete_chain - for each chain
        '''
        if len(self.sequence.keys()) == 0:
            print('Please get the sequence first')
            raise IndexError
        
        self.if_complete=1 # if not flow in then 1
        self.if_complete_chain = {}
        
        for chain in self.sequence:
            self.if_complete_chain[chain]=1 # if not flow in then 1
            for resi in self.sequence[chain]:
                if resi == 'NAN':
                    self.if_complete=0
                    self.if_complete_chain[chain]=0
                    break
        return self.if_complete, self.if_complete_chain


    def get_missing(self, seq):
        '''
        get_missing(self, seq)
        Compare self.sequence (from the get_seq) with the seq (str from the uniport)
        1. No missing
        2. Terminal missing
        3. Internal missing
        '''
        pass


    def PDB_loopmodel_refine(self, method='Rosetta'):
        '''
        Use different methods to model the missing sequence
        Methods:
        - pyRosetta
        - trRosetta
        remember to update the name.
        '''
        pass

    '''
    ========
    Protonation
    ========
    '''
    def get_protonation(self, ph=7.0, keep_id=0):
        '''
        Get protonation state based on PDB2PQR:
        1. Use PDB2PQR, save output to self.pqr_path
        2. Fix problems:
            - Metal center: 
            (detect donor(base on atom type) in a metal type based radiis) --> open for customize
                - Fix1: deprotonate all. 
                - Fix2: rotate if there're still lone pair left 
                - Fix3: run pka calculate containing ion (maybe pypka) and run Fix2 based on the result
            - Ligand:
                - Use OpenBable to protonate ligand by default
                # switch HIE HID when dealing with HIS
        save to self.path
        '''
        out_path=self.path_name+'_aH.pdb'
        self._get_file_path()
        self._get_protonation_pdb2pqr(ph=ph)
        self._protonation_Fix(out_path, ph=ph, keep_id=keep_id)
        self.path = out_path
        self._update_name()
        self.stru.name=self.name

 
    def _get_protonation_pdb2pqr(self,ffout='AMBER',ph=7.0,out_path=''):
        '''
        Use PDB2PQR to get the protonation state for current PDB. (self.path)
        current implementation just use the outer layer of PDB2PQR. Update to inner one and get more infomation in the furture. 
            (TARGET: 1. what is deleted from the structure // metal, ligand)
        
        save the result to self.pqr_path
        '''
        # set default value for output pqr path
        if len(out_path) == 0:
            self.pqr_path = self.path_name+'.pqr'
        else:
            self.pqr_path = out_path
        
        # input of PDB2PQR
        pdb2pqr_parser = build_pdb2pqr_parser()
        args = pdb2pqr_parser.parse_args(['--ff=PARSE','--ffout='+ffout,'--with-ph='+str(ph),self.path,self.pqr_path])
        # use context manager to hide output
        with HiddenPrints('./._get_protonation_pdb2pqr.log'):
            run_pdb2pqr(args)


    def _protonation_Fix(self, out_path, Metal_Fix='1', ph = 7.0, keep_id=0):
        '''
        Add in the missing atoms and run detailed fixing
        save to self.path
        '''

        # Add missing atom (from the PDB2PQR step. Update to func result after update the _get_protonation_pdb2pqr func)       
        # Now metal and ligand

        old_stru = Structure.fromPDB(self.path)
        new_stru = Structure.fromPDB(self.pqr_path)

        # find Metal center and combine with the pqr file
        metal_list = old_stru.get_metal_center()
        if len(metal_list) > 0:
            new_stru.add(metal_list, sort = 0)
            # fix metal environment
            new_stru.protonation_metal_fix(Fix = 1)

        # protonate ligands and combine with the pqr file
        if len(old_stru.ligands) > 0:
            lig_dir = self.dir+'/ligands/'
            mkdir(lig_dir)
            lig_paths = [(i,k) for i,j,k in old_stru.build_ligands(lig_dir, ifname=1)]

            new_ligs = []
            for lig_path, lig_name in lig_paths:
                new_lig_path, net_charge = self.protonate_ligand(lig_path, ph=ph)
                new_ligs.append(Ligand.fromPDB(new_lig_path, resi_name=lig_name, net_charge=net_charge, input_type='path'))
            new_stru.add(new_ligs, sort = 0)

        # PLACE HOLDER for other fix

        # build file
        if not keep_id:
            new_stru.sort()
        new_stru.build(out_path, keep_id=keep_id)
        self.stru = new_stru


    @classmethod
    def protonate_ligand(cls, path, method='PYBEL', ph = 7.0):
        '''
        Protonate the ligand from 'path' with 'method', provide out_path and net charge.
        ---------------
        method: PYBEL (default)
                Dimorphite (from https://durrantlab.pitt.edu/dimorphite-dl/) TODO seems better and with better python API.
                OPENBABEL (not working if block warning output)
        ph: 7.0 by default 
        '''
        outp1_path = path[:-4]+'_badname_aH.pdb'
        out_path = path[:-4]+'_aH.pdb'
        outm2_path = path[:-4]+'_aH.mol2'

        if method == 'OPENBABEL':
            # not working if block warning output for some reason
            # openbabel.obErrorLog.SetOutputLevel(0)
            obConversion = openbabel.OBConversion()
            obConversion.SetInAndOutFormats("pdb", "pdb")
            mol = openbabel.OBMol()
            obConversion.ReadFile(mol, path)
            mol.AddHydrogens(False, True, ph)
            obConversion.WriteFile(mol, out_path)
        if method == 'PYBEL':
            pybel.ob.obErrorLog.SetOutputLevel(0)
            mol = next(pybel.readfile('pdb', path))
            mol.OBMol.AddHydrogens(False, True, ph)
            mol.write('pdb', outp1_path, overwrite=True)
            # fix atom label abd determing net charge
            cls._fix_ob_output(outp1_path, out_path)
            # determine partial charge
            # > METHOD 1<
            net_charge = cls._ob_pdb_charge(outp1_path)
            # > METHOD 2 <
            # mol.write('mol2', outm2_path, overwrite=True)
            # mol = next(pybel.readfile('mol2', outm2_path))
            # net_charge=0
            # for atom in mol:
            #     net_charge=net_charge+atom.formalcharge
        if method == 'Dimorphite':
            pass
        return out_path, net_charge


    @classmethod
    def _fix_ob_output(cls, pdb_path, out_path):
        '''
        fix atom label in pdb_pat write to out_path
        ---------
        according to tleap output, the name could be just *counting* the element start from ' ' to number
        '''
        with open(pdb_path) as f:
            with open(out_path, 'w') as of:
                # count element in a dict
                ele_count={}
                pdb_ls = PDB_line.fromlines(f.read())
                for pdb_l in pdb_ls:
                    if pdb_l.line_type == 'HETATM' or pdb_l.line_type == 'ATOM':
                        ele = pdb_l.get_element()
                        # determine the element count
                        try:
                            # rename if more than one (add count)
                            ele_count[ele] += 1
                            pdb_l.atom_name = ele+str(ele_count[ele])
                        except KeyError:
                            ele_count[ele] = 0
                            pdb_l.atom_name = ele
                        of.write(pdb_l.build())
               

    @classmethod
    def _ob_pdb_charge(cls, pdb_path):
        '''
        extract net charge from openbabel exported pdb file
        '''
        with open(pdb_path) as f:
            net_charge=0
            pdb_ls = PDB_line.fromlines(f.read())
            for pdb_l in pdb_ls:
                if pdb_l.line_type == 'HETATM' or pdb_l.line_type == 'ATOM':
                    if len(pdb_l.get_charge()) != 0:
                        charge = pdb_l.charge[::-1]
                        if Config.debug > 1:
                            print('Found formal charge: '+pdb_l.atom_name+' '+charge)
                        net_charge = net_charge + int(charge)
            return net_charge


    '''
    ========
    Mutation
    ========
    '''

    def PDB2PDBwLeap(self):
        '''
        Apply mutations using tleap. Save mutated structure PDB in self.path
        ------------------------------
        Use MutaFlag in self.MutaFlags
        Grammer (from Add_MutaFlag):
        X : Original residue name. Leave X if unknow. 
            Only used for build filenames. **Do not affect any calculation.**
        A : Chain index. Determine by 'TER' marks in the PDB file. (Do not consider chain_indexs in the original file.)
        11: Residue index. Strictly correponding residue indexes in the original file. (NO sort applied)
        Y : Target residue name.  

        **WARNING** if there are multiple mutations on the same index, only the first one will be used.
        '''

        #Judge if there are same MutaIndex (c_id + r_id)
        for i in range(len(self.MutaFlags)):
            for j in range(len(self.MutaFlags)):
                if i >= j:
                    pass
                else:
                    if (self.MutaFlags[i][1], self.MutaFlags[i][2]) == (self.MutaFlags[j][1], self.MutaFlags[j][2]):
                        if Config.debug >= 1:
                            print("PDB2PDBwLeap: There are multiple mutations at the same index, only the first one will be used: "+self.MutaFlags[i][0]+self.MutaFlags[i][1]+self.MutaFlags[i][2])

        # Prepare a label for the filename
        tot_Flag_name=''
        for Flag in self.MutaFlags:
            Flag_name=self._build_MutaName(Flag)
            tot_Flag_name=tot_Flag_name+'_'+Flag_name

        # Operate the PDB
        out_PDB_path1=self.cache_path+'/'+self.name+tot_Flag_name+'_tmp.pdb'
        out_PDB_path2=self.path_name+tot_Flag_name+'.pdb'

        self._get_file_path()
        with open(self.path,'r') as f:
            with open(out_PDB_path1,'w') as of:
                chain_count = 1
                for line in f:
                    pdb_l = PDB_line(line)
                                        
                    TER_flag = 0
                    if pdb_l.line_type == 'TER':
                        TER_flag = 1
                    # add chain count in next loop for next line
                    if TER_flag:
                        chain_count += 1
                    match=0
                    # only match in the dataline and keep all non data lines
                    if pdb_l.line_type == 'ATOM':
                        for Flag in self.MutaFlags:
                            # Test for every Flag for every lines
                            t_chain_id=Flag[1]
                            t_resi_id =Flag[2]

                            if chr(64+chain_count) == t_chain_id:
                                if pdb_l.resi_id == int(t_resi_id):
                                    
                                    # do not write old line if match a MutaFlag
                                    match=1
                                    # Keep OldAtoms of targeted old residue
                                    resi_2 = Flag[3]
                                    OldAtoms=['N','H','CA','HA','CB','C','O']
                                    #fix for mutations of Gly & Pro
                                    if resi_2 == 'G':
                                        OldAtoms=['N','H','CA','C','O']
                                    if resi_2 == 'P':
                                        OldAtoms=['N','CA','HA','CB','C','O']

                                    for i in OldAtoms:
                                        if i == pdb_l.atom_name:
                                            new_line=line[:17]+Resi_map[resi_2]+line[20:]                                        
                                            of.write(new_line)
                                            break                                
                                    #Dont run for other Flags after first Flag matches.
                                    break

                    if not match:               
                        of.write(line)


        # Run tLeap 
        #make input
        leapin_path = self.cache_path+'/leap_P2PwL.in'
        leap_input=open(leapin_path,'w')
        leap_input.write('source leaprc.protein.ff14SB\n')
        leap_input.write('a = loadpdb '+out_PDB_path1+'\n')
        leap_input.write('savepdb a '+out_PDB_path2+'\n')
        leap_input.write('quit\n')
        leap_input.close()
        #run
        os.system('tleap -s -f '+leapin_path+' > '+self.cache_path+'/leap_P2PwL.out')
        if Config.debug <= 1:
            os.system('rm leap.log')

        #Update the file
        self.path = out_PDB_path2
        self._update_name()

        return self.path


    def Add_MutaFlag(self,Flag = 'r'):
        '''
        Input: 
        Flags or "random"
        ----------------------------------------------------
        Flag    (e.g. XA11Y) Can be a str or a list of str (a list of flags).
        ----------------------------------------------------
        Append self.MutaFlags with the Flag.
        Grammer:
        X : Original residue name. Leave X if unknow. 
            Only used for build filenames. **Do not affect any calculation.**
        A : Chain index. Determine by 'TER' marks in the PDB file. (Do not consider chain_indexs in the original file.)
        11: Residue index. Strictly correponding residue indexes in the original file. (NO sort applied)
        Y : Target residue name.  
        ----------------------------------------------------
        'random' or 'r' (default)
        ----------------------------------------------------
        return a label of mutations
        '''

        if type(Flag) == str:

            if Flag == 'r' or Flag == 'random':
                resi_1 = ''
                resi_2 = ''
                Muta_c_id = ''
                Muta_r_id = ''

                # Flag Generation：
                # Random over the self.stru. Strictly correponding residue indexes in the original file. (no sort applied)
                self.get_stru()
                # random over the structure "protein" part.
                chain = choice(self.stru.chains)
                resi = choice(chain.residues)
                Muta_c_id = chain.id
                Muta_r_id = str(resi.id)
                if resi.name in Resi_map2:
                    resi_1 = Resi_map2[resi.name]
                else:
                    resi_1 = resi.name
                # random over the residue list
                resi_2 = choice(Resi_list)

                MutaFlag = (resi_1, Muta_c_id, Muta_r_id ,resi_2)
                self.MutaFlags.append(MutaFlag)

            else:
                MutaFlag = self._read_MutaFlag(Flag)
                self.MutaFlags.append(MutaFlag)

        if type(Flag) == list:
            for i in Flag:
                MutaFlag = self._read_MutaFlag(i)
                self.MutaFlags.append(MutaFlag)

        if Config.debug >= 1:
            print('Current MutaFlags:')
            for flag in self.MutaFlags:
                print(self._build_MutaName(flag))

        label=''
        for flag in self.MutaFlags:
            label=label+'_'+self._build_MutaName(flag) 
        return label
                

    def _read_MutaFlag(self, Flag):
        '''
        decode the manually input MutaFlag. Return (resi_1, chain_id, resi_id, resi_2)
        --------------
        Grammer(XA11Y):
        X : Original residue name. Leave X if unknow. 
            Only used for build filenames. **Do not affect any calculation.**
        A : Chain index. Determine by 'TER' marks in the PDB file. (Do not consider chain_indexs in the original file.)
        11: Residue index. Strictly correponding residue indexes in the original file. (NO sort applied)
        Y : Target residue name.

        the later 3 will go through a san check to make sure they are within the range:
        A : chain.id range in self.stru.chains
        11: resi.id range in self.stru.chain[int].residues
        Y : Resi_list
        '''
        pattern = r'([A-Z])([A-Z])?([0-9]+)([A-Z])'
        F_match = re.match(pattern, Flag)
        if F_match is None:
            raise Exception('_read_MutaFlag: Required format: XA123Y (or X123Y indicating the first chain)')
        
        resi_1 = F_match.group(1)
        chain_id = F_match.group(2)
        resi_id = str(F_match.group(3))
        resi_2 = F_match.group(4)

        # san check of the manual input
        self.get_stru()
        chain_id_list = [i.id for i in self.stru.chains]
        if not chain_id in chain_id_list:
            raise Exception('_read_MutaFlag: San check failed. Input chain id in not in range.'+line_feed+' range: '+ repr(chain_id_list))
        chain_int = ord(chain_id)-65
        resi_id_list = [str(i.id) for i in self.stru.chains[chain_int].residues]
        if not resi_id in resi_id_list:
            raise Exception('_read_MutaFlag: San check failed. Input resi id in not in range.'+line_feed+' range: '+ repr(resi_id_list))
        if not resi_2 in Resi_list:
            raise Exception('_read_MutaFlag: Only support mutate to the known 21 residues. AmberMaps.Resi_list: '+ repr(Resi_list))

        # default
        if F_match.group(2) is None:
            chain_id = 'A'
            if Config.debug >= 1:
                print('_read_MutaFlag: No chain_id is provided! Mutate in the first chain by default. Input: ' + Flag)   

        return (resi_1, chain_id, resi_id, resi_2)
    

    def _build_MutaName(self, Flag):
        '''
        Take a MutaFlag Tuple and return a str of name
        '''
        return Flag[0]+Flag[1]+Flag[2]+Flag[3]


    def PDBMin(self,cycle=2000):
        '''
        Run a minization use self.prmtop and self.inpcrd and setting form class Config.
        --------------------------------------------------
        Save changed PDB to self.path (containing water and ions)
        Mainly used for remove bad contact from PDB2PDBwLeap.
        '''
        
        out4_PDB_path=self.path_name+'_min.pdb'

        #make sander input
        min_dir = self.cache_path+'/PDBMin'
        minin_path = min_dir + '/min.in'
        minout_path = min_dir + '/min.out'
        minrst_path = min_dir + '/min.rst'
        mkdir(min_dir)
        min_input=open(minin_path,'w')
        min_input.write('Minimize'+line_feed)
        min_input.write(' &cntrl'+line_feed)
        min_input.write('  imin=1,'+line_feed)
        min_input.write('  ntx=1,'+line_feed)
        min_input.write('  irest=0,'+line_feed)
        min_input.write('  maxcyc='+str(cycle)+','+line_feed)
        min_input.write('  ncyc='+str(int(0.5*cycle))+','+line_feed)
        min_input.write('  ntpr='+str(int(0.2*cycle))+','+line_feed)
        min_input.write('  ntwx=0,'+line_feed)
        min_input.write('  cut=8.0,'+line_feed)
        min_input.write(' /'+line_feed)
        min_input.close()
    

        #run
        if Config.debug >= 1:
            print('running: '+Config.PC_cmd +' '+ Config.Amber.AmberHome + '/bin/sander.MPI -O -i '+minin_path+' -o '+minout_path+' -p '+self.prmtop_path+' -c '+self.inpcrd_path+' -r '+minrst_path)
        os.system(Config.PC_cmd +' '+ Config.Amber.AmberHome + '/bin/sander.MPI -O -i '+minin_path+' -o '+minout_path+' -p '+self.prmtop_path+' -c '+self.inpcrd_path+' -r '+minrst_path)
        #rst2pdb
        os.system('ambpdb -p '+self.prmtop_path+' -c '+minrst_path+' > '+out4_PDB_path)
        os.system('mv '+self.prmtop_path+' '+self.inpcrd_path+' '+min_dir)

        self.path = out4_PDB_path
        self._update_name()
        self.prmtop_path=min_dir+'/'+self.prmtop_path
        self.inpcrd_path=min_dir+'/'+self.inpcrd_path

        return self.path


    def rm_allH(self, ff='Amber'):
        '''
        remove wrong hydrogens added by leap after mutation (In the case that the input file was a H-less one from crystal.)
        '''
        # out path
        o_path=self.path_name+'_rmH.pdb'
        # H list
        H_namelist=[]
        for name in Resi_Ele_map[ff]:
            if Resi_Ele_map[ff][name] == 'H':
                H_namelist.append(name)

        with open(self.path) as f:
            with open(o_path,'w') as of:
                for line in f:
                    if line[12:16].strip() in H_namelist:
                        continue
                    of.write(line)

        
    '''
    ========
    Gerneral MD
    ========
    '''

    def PDB2FF(self, o_path='', lig_method='AM1BCC', renew_lig=0, ifsavepdb=0):
        '''
        PDB2FF(self, o_path='')
        --------------------
        o_path contral where the leap.in and leap.log go: has to contain a / at the end (e.g.: ./dir/)
        --------------------
        chains:
        ligand: - less junk files if your workflow contains a protonation step in advance.  
        metal:
        '''
        # check and generate self.stru
        self.get_stru()

        # build things seperately
        lig_dir = self.dir+'/ligands/'
        met_dir = self.dir+'/metalcenters/'
        mkdir(lig_dir)
        mkdir(met_dir)

        ligands_pathNchrg = self.stru.build_ligands(lig_dir, ifcharge=1, ifunique=1)
        # metalcenters_path = self.stru.build_metalcenters(met_dir)
        # parm
        ligand_parm_paths = self._ligand_parm(ligands_pathNchrg, method=lig_method, renew=renew_lig)
        # self._metal_parm(metalcenters_path)
        # combine
        if o_path != '':
            mkdir(o_path)
        self._combine_parm(ligand_parm_paths, o_path=o_path, ifsavepdb=ifsavepdb)
        if ifsavepdb:
            self.path = self.path_name+'_ff.pdb'
            self._update_name()
        
        return (self.prmtop_path,self.inpcrd_path)

    
    def _ligand_parm(self, paths, method='AM1BCC', renew=0):
        '''
        Turn ligands to prepi (w/net charge), parameterize with parmchk
        return [(perpi_1, frcmod_1), ...]
        -----------
        method  : method use for ligand charge. Only support AM1BCC now.
        renew   : 0:(default) use old parm files if exist. 1: renew parm files everytime
        * WARN: The parm file for ligand will always be like xxx/ligand_1.frcmod. Remember to enable renew when different object is sharing a same path.
        * BUG: Antechamber has a bug that if current dir has temp files from previous antechamber run (ANTECHAMBER_AC.AC, etc.) sqm will fail. Now remove them everytime.
        '''
        parm_paths = []

        for lig_pdb, net_charge in paths:
            if method == 'AM1BCC':
                out_prepi = lig_pdb[:-3]+'prepin'
                out_frcmod = lig_pdb[:-3]+'frcmod'
                if os.path.isfile(out_prepi) and os.path.isfile(out_frcmod) and not renew:
                    if Config.debug >= 1:
                        print('Parm files exist: ' + out_prepi + ' ' + out_frcmod)
                        print('Using old parm files.')
                else:
                    #gen prepi (net charge and correct protonation state is important)
                    os.system(Config.Amber.AmberHome+'/bin/antechamber -i '+lig_pdb+' -fi pdb -o '+out_prepi+' -fo prepi -c bcc -s 0 -nc '+str(net_charge))
                    if Config.debug <= 1:
                        os.system('rm ANTECHAMBER* ATOMTYPE.INF NEWPDB.PDB PREP.INF sqm.pdb sqm.in sqm.out')
                    #gen frcmod
                    os.system(Config.Amber.AmberHome+'/bin/parmchk2 -i '+out_prepi+' -f prepi -o '+out_frcmod)                
                #record
                parm_paths.append((out_prepi, out_frcmod))

        return parm_paths


    def _combine_parm(self, lig_parms, o_path='', ifsavepdb=0, ifsolve=1, box_type=Config.Amber.box_type, box_size=Config.Amber.box_size):
        '''
        combine different parmeter files and make finally inpcrd and prmtop
        -------
        structure: pdb
        ligands: prepi, frcmod
        metalcenters, artificial residues: TODO
        '''
        leap_path= self.cache_path+'/leap.in'
        sol_path= self.path_name+'_ff.pdb'
        with open(leap_path, 'w') as of:
            of.write('source leaprc.protein.ff14SB'+line_feed)
            of.write('source leaprc.gaff'+line_feed)
            of.write('source leaprc.water.tip3p'+line_feed)
            # ligands
            for prepi, frcmod in lig_parms:
                of.write('loadAmberParams '+frcmod+line_feed)
                of.write('loadAmberPrep '+prepi+line_feed)
            of.write('a = loadpdb '+self.path+line_feed)
            of.write('center a'+line_feed)
            # solvation
            if ifsolve:
                of.write('addions a Na+ 0'+line_feed)
                of.write('addions a Cl- 0'+line_feed)
                if box_type == 'box':
                    of.write('solvatebox a TIP3PBOX '+box_size+line_feed)
                if box_type == 'oct':
                    of.write('solvateOct a TIP3PBOX '+box_size+line_feed)
                if box_type != 'box' and box_type != 'oct':
                    raise Exception('PDB._combine_parm().box_type: Only support box and oct now!')
            # save
            if o_path == '':
                of.write('saveamberparm a '+self.path_name+'.prmtop '+self.path_name+'.inpcrd'+line_feed)
                self.prmtop_path=self.path_name+'.prmtop'
                self.inpcrd_path=self.path_name+'.inpcrd'
            else:
                of.write('saveamberparm a '+o_path+self.name+'.prmtop '+o_path+self.name+'.inpcrd'+line_feed)
                self.prmtop_path=o_path+self.name+'.prmtop'
                self.inpcrd_path=o_path+self.name+'.inpcrd'
            if ifsavepdb:
                of.write('savepdb a '+sol_path+line_feed)
            of.write('quit'+line_feed)

        os.system('tleap -s -f '+leap_path+' > '+leap_path[:-2]+'out')

        return self.prmtop_path, self.inpcrd_path


    def rm_wat(self):
        '''
        Remove water and ion for the pdb. Remians the same if there's no water or ion.
        Now only skip [Na+,Cl-,WAT,HOH] // Append more in the future.
        Save changed files into self.path.
        TODO: need to support key water.
        '''
        out_path = self.path_name+'_rmW.pdb'
        self._get_file_path()
        with open(self.path) as f:
            with open(out_path,'w') as of:
                skip_list=['Na+','Cl-','WAT','HOH']
                change_flag=0
                for line in f:
                    PDB_l = PDB_line(line)
                    #Skip some lines
                    skip_flag=0
                    #skip the CRYST1 line
                    if line[:6] == 'CRYST1':
                        change_flag=1
                        continue
                    #keep TER and END
                    if line[:3] == 'TER' or line[:3] == 'END':
                        of.write(line)
                        continue

                    #skip the water and ion(Append in the future)
                    for i in skip_list:
                        if PDB_l.resi_name == i:
                            skip_flag=1
                            break
                    if skip_flag:
                        change_flag=1
                        continue

                    of.write(line)
                if not change_flag:
                    print('rm_wat(): No change.')

        self.path=out_path
        self._update_name()

        return self.path


    def PDBMD(self, tag='', o_dir=''):
        '''
        Use self.prmtop_path and self.inpcrd_path to initilize a MD simulation.
        The default MD configuration settings are assigned by class Config.Amber.
        * User can also set MD configuration for the current object by assigning values in self.conf_xxxx.
        * e.g.: self.conf_heat['nstlim'] = 50000
        --------------
        o_dir   : Write files in o_dir (current self.dir/MD by default).
        tag     : tag the name of the MD folder
        Return the nc path of the prod step.
        '''
        # make folder
        if o_dir == '':
            o_dir = self.dir+'/MD'+tag
        mkdir(o_dir)

        # build input file (use self.MD_conf_xxxx)
        min_path = self._build_MD_min(o_dir)
        heat_path = self._build_MD_heat(o_dir)
        equi_path = self._build_MD_equi(o_dir)
        prod_path = self._build_MD_prod(o_dir)

        # run sander
        if Config.debug >= 1:
            print('running: '+Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+min_path +' -o '+o_dir+'/min.out -p '+self.prmtop_path+' -c '+self.inpcrd_path+' -r '+o_dir+'/min.rst -ref '+self.inpcrd_path)
        os.system(Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+min_path +' -o '+o_dir+'/min.out -p '+self.prmtop_path+' -c '+self.inpcrd_path+' -r '+o_dir+'/min.rst -ref '+self.inpcrd_path)
        if Config.debug >= 1:
            print('running: '+Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+heat_path+' -o '+o_dir+'/heat.out -p '+self.prmtop_path+' -c '+o_dir+'/min.rst -ref ' +o_dir+'/min.rst -r ' +o_dir+'/heat.rst')
        os.system(Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+heat_path+' -o '+o_dir+'/heat.out -p '+self.prmtop_path+' -c '+o_dir+'/min.rst -ref ' +o_dir+'/min.rst -r ' +o_dir+'/heat.rst')
        if Config.debug >= 1:
            print('running: '+Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+equi_path+' -o '+o_dir+'/equi.out -p '+self.prmtop_path+' -c '+o_dir+'/heat.rst -ref '+o_dir+'/heat.rst -r '+o_dir+'/equi.rst -x '+o_dir+'/equi.nc')
        os.system(Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+equi_path+' -o '+o_dir+'/equi.out -p '+self.prmtop_path+' -c '+o_dir+'/heat.rst -ref '+o_dir+'/heat.rst -r '+o_dir+'/equi.rst -x '+o_dir+'/equi.nc')
        if Config.debug >= 1:
            print('running: '+Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+prod_path+' -o '+o_dir+'/prod.out -p '+self.prmtop_path+' -c '+o_dir+'/equi.rst -ref '+o_dir+'/equi.rst -r '+o_dir+'/prod.rst -x '+o_dir+'/prod.nc')
        os.system(Config.PC_cmd +' '+ Config.Amber.AmberHome +'/bin/sander.MPI -O -i '+prod_path+' -o '+o_dir+'/prod.out -p '+self.prmtop_path+' -c '+o_dir+'/equi.rst -ref '+o_dir+'/equi.rst -r '+o_dir+'/prod.rst -x '+o_dir+'/prod.nc')

        return o_dir+'/prod.nc'


    def _build_MD_min(self, o_dir):
        '''
        Build configuration file for a minimization job
        See default value Config.Amber.conf_min
        '''
        #path
        o_path=o_dir+'/min.in'
        #maxcyc related
        maxcyc = self.conf_min['maxcyc']
        if self.conf_min['ncyc'] == '0.5maxcyc':
            ncyc = str(int(0.5 * maxcyc))
        if self.conf_min['ntpr'] == '0.01maxcyc':
            ntpr = str(int(0.01 * maxcyc))
        maxcyc = str(maxcyc)
        #restrain related
        if self.conf_min['ntr'] == '1':
            ntr_line = '  ntr   = '+self.conf_min['ntr']+',	 restraint_wt = '+self.conf_min['restraint_wt']+', restraintmask = '+self.conf_min['restraintmask']+','+line_feed
        else:
            ntr_line = ''

        #text        
        conf_str='''Minimize
 &cntrl
  imin  = 1,  ntx   = 1,  irest = 0,
  ntc   = '''+self.conf_min['ntc']+''',    ntf = '''+self.conf_min['ntf']+''',
  cut   = '''+self.conf_min['cut']+''',
  maxcyc= '''+maxcyc+''', ncyc  = '''+ncyc+''',
  ntpr  = '''+ntpr+''', ntwx  = 0,
'''+ntr_line+''' /
'''
        #write
        with open(o_path,'w') as of:
            of.write(conf_str)
        return o_path


    def _build_MD_heat(self, o_dir):
        '''
        Build configuration file for a heat job
        See default value Config.Amber.conf_heat
        '''
        #path
        o_path=o_dir+'/heat.in'

        # nstlim related
        nstlim=self.conf_heat['nstlim']
        if self.conf_heat['A_istep2'] == '0.9nstlim':
            A_istep2=str(int(nstlim*0.9))
        if self.conf_heat['B_istep1'] == 'A_istep2+1':
            B_istep1=str(int(A_istep2)+1)
        if self.conf_heat['ntpr'] == '0.01nstlim':
            ntpr = str(int(nstlim*0.01))
        if self.conf_heat['ntwx'] == 'nstlim':
            ntwx = str(nstlim)
        nstlim = str(nstlim)
        #restrain related
        if self.conf_heat['ntr'] == '1':
            ntr_line = '  ntr   = '+self.conf_heat['ntr']+', restraint_wt = '+self.conf_heat['restraint_wt']+', restraintmask = '+self.conf_heat['restraintmask']+','+line_feed
        else:
            ntr_line = ''

        conf_str='''Heat
 &cntrl
  imin  = 0,  ntx = 1, irest = 0,
  ntc   = '''+self.conf_heat['ntc']+''', ntf = '''+self.conf_heat['ntf']+''',
  cut   = '''+self.conf_heat['cut']+''',
  nstlim= '''+nstlim+''', dt= '''+self.conf_heat['dt']+''',
  tempi = '''+self.conf_heat['tempi']+''',  temp0='''+self.conf_heat['temp0']+''',  
  ntpr  = '''+ntpr+''',  ntwx='''+ntwx+''',
  ntt   = '''+self.conf_heat['ntt']+''', gamma_ln = '''+self.conf_heat['gamma_ln']+''',
  ntb   = 1,  ntp = 0,
  iwrap = '''+self.conf_heat['iwarp']+''',
  nmropt= 1,
  ig    = -1,
'''+ntr_line+''' /
 &wt
  type  = 'TEMP0',
  istep1= 0, istep2='''+A_istep2+''',
  value1= '''+self.conf_heat['tempi']+''', value2='''+self.conf_heat['temp0']+''',
 /
 &wt
  type  = 'TEMP0',
  istep1= '''+B_istep1+''', istep2='''+nstlim+''',
  value1= '''+self.conf_heat['temp0']+''', value2='''+self.conf_heat['temp0']+''',
 /
 &wt
  type  = 'END',
 /
'''
        #write
        with open(o_path,'w') as of:
            of.write(conf_str)
        return o_path


    def _build_MD_equi(self, o_dir):
        '''
        Build configuration file for the equilibration step
        See default value Config.Amber.conf_equi
        default ntwx -> 10ps
        '''
        #path
        o_path=o_dir+'/equi.in'

        # nstlim related
        nstlim=self.conf_equi['nstlim']
        if self.conf_equi['ntpr'] == '0.002nstlim':
            ntpr = str(int(nstlim*0.002))
        nstlim = str(nstlim)
        #restrain related
        if self.conf_equi['ntr'] == '1':
            ntr_line = '  ntr   = '+self.conf_equi['ntr']+', restraint_wt = '+self.conf_equi['restraint_wt']+', restraintmask = '+self.conf_equi['restraintmask']+','+line_feed
        else:
            ntr_line = ''


        conf_str='''Equilibration:constant pressure
 &cntrl
  imin  = 0,  ntx = '''+self.conf_equi['ntx']+''',  irest = '''+self.conf_equi['irest']+''',
  ntf   = '''+self.conf_equi['ntf']+''',  ntc = '''+self.conf_equi['ntc']+''',
  nstlim= '''+nstlim+''', dt= '''+self.conf_equi['dt']+''',
  cut   = '''+self.conf_equi['cut']+''',
  temp0 = '''+self.conf_equi['temp0']+''',
  ntpr  = '''+ntpr+''', ntwx = '''+self.conf_equi['ntwx']+''',
  ntt   = '''+self.conf_equi['ntt']+''', gamma_ln = '''+self.conf_equi['gamma_ln']+''',
  ntb   = 2,  ntp = 1,
  iwrap = '''+self.conf_equi['iwarp']+''',
  ig    = -1,
'''+ntr_line+''' /
'''
        #write
        with open(o_path,'w') as of:
            of.write(conf_str)
        return o_path



    def _build_MD_prod(self, o_dir):
        '''
        Build configuration file for the production step
        See default value Config.Amber.conf_prod
        default ntwx -> 10ps
        '''
        #path
        o_path=o_dir+'/prod.in'

        # nstlim related
        nstlim=self.conf_prod['nstlim']
        if self.conf_prod['ntpr'] == '0.001nstlim':
            ntpr = str(int(nstlim*0.001))
        nstlim = str(nstlim)
        #restrain related
        if self.conf_prod['ntr'] == '1':
            ntr_line = '  ntr   = '+self.conf_prod['ntr']+', restraint_wt = '+self.conf_prod['restraint_wt']+', restraintmask = '+self.conf_prod['restraintmask']+','+line_feed
        else:
            ntr_line = ''        

        conf_str='''Production: constant pressure
 &cntrl
  imin  = 0, ntx = '''+self.conf_prod['ntx']+''', irest = '''+self.conf_prod['irest']+''',
  ntf   = '''+self.conf_prod['ntf']+''',  ntc = '''+self.conf_prod['ntc']+''',
  nstlim= '''+nstlim+''', dt= '''+self.conf_prod['dt']+''',
  cut   = '''+self.conf_prod['cut']+''',
  temp0 = '''+self.conf_prod['temp0']+''',
  ntpr  = '''+ntpr+''', ntwx = '''+self.conf_prod['ntwx']+''',
  ntt   = '''+self.conf_prod['ntt']+''', gamma_ln = '''+self.conf_prod['gamma_ln']+''',
  ntb   = 2,  ntp = 1,
  iwrap = '''+self.conf_prod['iwarp']+''',
  ig    = -1,
'''+ntr_line+''' /
'''        
        #write
        with open(o_path,'w') as of:
            of.write(conf_str)
        return o_path
    

    def reset_MD_conf(self):
        '''
        reset MD configuration of current object to default. 
        '''
        self.conf_min = Config.Amber.conf_min
        self.conf_heat = Config.Amber.conf_heat
        self.conf_equi = Config.Amber.conf_equi
        self.conf_prod = Config.Amber.conf_prod


    def show_MD_conf(self):
        '''
        Show MD configuration of current object. 
        '''
        print('Min :     '+repr(self.conf_min))
        print('Heat:     '+repr(self.conf_heat))
        print('Equi:     '+repr(self.conf_equi))
        print('Prod:     '+repr(self.conf_prod))

    '''
    ========
    QM/MM
    ========
    '''
    # 需要确保MD的结构和模板结构完全一致（溶剂、 配体）
    def PDB2QMMM(self, o_dir='',tag='', work_type='spe', qm='g16', keywords='', prmtop_path=None):
        '''
        generate QMMM input template based on [connectivity, atom order, work type, layer/freeze settings, charge settings]
        * NEED TO SET LAYER BY ATOM INDEX OR SELECT A LAYER PRESET (use Config.Gaussian.layer_preset and Config.Gaussian.layer_atoms)
        --------
        qm          : QM program (default: g16 / Gaussian16)
        work_type   : QMMM calculation type (default: spe)
        o_dir       : out put directory of the input file (default: self.dir/QMMM/ )
        tag         : folder name tag for potential multiple mutations
        keywords    : additional keywords add to the work_type correlated route
        prmtop_path : provide prmtop file for determining charge and spin. use self.prmtop by default
        <see more options in Config.Gaussian>
        ========
        Gaussian
        ========
        # route section (from config module / leave work type as an inp arg)
        # charge and spin
        # coordinate 
        	- atom label (from .lib)
        	- atom charge
        	- freeze part (general option / some presupposition / freeze MM) 
        	- layer (same as above)
        	- xyz (1. new system 2. existing template (do we still need?) -- from pdb / mdcrd / gout) ref: ONIOM_template_tool
        # connectivity
        # missing parameters (ligand related?)
        ---------
        In Config.Gaussian 
        ---------
        n_cores     : Cores for gaussian job (higher pirority)
        max_core    : Per core memory in MB for gaussian job (higher pirority)
        keywords    : a list of keywords that joined together when build
        layer_preset：default preset id copied to self.layer_preset
        layer_atoms : default layer_atoms copied to self.layer_atoms
        
        *om_lvl     : *(can only be edit manually before loading the module) oniom method level
        '''
        # san check
        support_work_type=['spe','opt','tsopt']
        if work_type not in support_work_type:
            raise Exception('PDB2QMMM.work_type : only support: '+repr(support_work_type))
        support_qm=['g16']
        if qm not in support_qm:
            raise Exception('PDB2QMMM.qm: only support: '+repr(support_qm))
        # make folder
        if o_dir == '':
            o_dir = self.dir+'/QMMM'+tag
        mkdir(o_dir)
        # file path and name
        o_name = self.name+'_QMMM'
        o_path = o_dir+'/'+o_name+'.gjf'
        #get layer
        self._get_oniom_layer()

        # build template
        if qm == 'g16':
            self.route = self._get_oniom_g16_route(work_type, o_name, key_words=keywords)
            title = 'ONIOM input template generated by PDB2QMMM of XXX'+line_feed
            chrgspin = self._get_oniom_chrgspin(prmtop_path=prmtop_path)
            coord = self._get_oniom_g16_coord()
            cnt_table = self._get_oniom_cnt()
            add_prm = self._get_oniom_g16_add_prm() # test for rules of missing parameters
            
            #combine and write 
            with open(o_path,'w') as of:
                of.write(self.route) 
                of.write(line_feed) 
                of.write(title)
                of.write(line_feed)
                of.write(chrgspin)
                of.write(line_feed)
                of.write(coord)
                of.write(line_feed)
                of.write(cnt_table)
                of.write(line_feed)
                of.write(add_prm)

        return o_path


    def _get_oniom_layer(self):
        '''
        get oniom layer base on self.layer_atoms or self.layer_preset
        save a Layer object to self.layer
        '''
        #  san check (need at least a set or a preset mode)
        if self.layer_atoms == [] and self.layer_preset == 0:
            raise Exception('PDB2QMMM: need layer setting. Please use self.set_oniom_layer.')
        # layer_atoms are in higher pirority
        if self.layer_atoms != []:
            self.layer = Layer(self, self.layer_atoms)
        else:
            self.layer = Layer.preset(self, self.layer_preset)


    def _get_oniom_g16_route(self, work_type, chk_name='QMMM', key_words=''):
        '''
        generate gaussian 16 ONIOM route section. Base on settings in the config module.
        -------
        work_type   : ONIOM calculation type (support: spe, ...)
        chk_name    : filename of chk (QMMM.chk by default / self.name + _QMMM.chk in the default workflow use.)
        key_words   : allow additional key words
        -------
        support edit keywords directly in module Config
        '''
        chk = r'%chk='+chk_name+'.chk' + line_feed
        proc = '%nprocshared='+str(Config.Gaussian.n_cores) + line_feed
        mem = '%mem=' + str(Config.Gaussian.n_cores * Config.Gaussian.max_core) + 'MB' + line_feed
        if type(key_words) == str and key_words != '':
            keyword_line = '# '+' '.join(Config.Gaussian.keywords[work_type]+[key_words,]) + line_feed
        if type(key_words) == list:
            keyword_line = '# '+' '.join(Config.Gaussian.keywords[work_type]+key_words) + line_feed

        route = chk + proc + mem + keyword_line
        return route


    def _get_oniom_chrgspin(self, prmtop_path=None, spin_list=[1,1]):
        '''
        Determing charge and spin for each ONIOM layers. Base on *prmtop file* and layer settings in the *config* module.
        '''
        chrgspin = None
        # san check
        if prmtop_path == None:
            if self.prmtop_path == None:
                raise Exception('Please provide or use PDB2FF() to generate a prmtop file before PDB2QMMM')
            prmtop_path=self.prmtop_path

        # get charge list
        self.chrg_list_all = PDB.get_charge_list(prmtop_path)
        # init
        self.layer_chrgspin=[]
        for j in range(len(self.layer)):
            self.layer_chrgspin.append(float(0))
        # add charge to layers
        for i, chrg in enumerate(self.chrg_list_all):
            for j, layer in enumerate(self.layer):
                if i+1 in layer:
                    self.layer_chrgspin[j] += chrg

        # add spin
        if len(self.layer_chrgspin) != len(spin_list):
            raise Exception('spin specification need to match the layer setting. e.g.: spin_list=[h_spin, l_spin]')
        for i,spin in enumerate(spin_list):
            self.layer_chrgspin[i] = (self.layer_chrgspin[i], spin)    
        
        if len(self.layer) == 2:
            c1 = str(round(self.layer_chrgspin[0][0]))
            s1 = str(round(self.layer_chrgspin[0][1]))
            c2 = str(round(self.layer_chrgspin[1][0]))
            s2 = str(round(self.layer_chrgspin[1][1]))
            c3 = c2
            s3 = s2
            chrgspin = ' '.join([c1,s1,c2,s2,c3,s3])
        else:
            raise Exception('Only support 2 layers writing charge and spin. Update in the future')

        return chrgspin


    def _get_oniom_g16_coord(self):
        '''
        generate coordinate line. Base on *structure* and layer settings in the *config* module.
        ---------------
        for a coord line:
            - element name
        	- atom name (from .lib)
        	- atom charge
        	- freeze part (general option / some presupposition) 
        	- xyz (from self.stru)
        	- layer (general option / some presupposition) 需要label一个对接氢原子
        '''
        coord='TODO'
        return coord
    
    
    def _get_oniom_cnt(self):
        oniom_cnt='TODO'
        return oniom_cnt


    def _get_oniom_g16_add_prm(self):
        oniom_g16_add_prm='TODO'
        return oniom_g16_add_prm

    @classmethod
    def get_charge_list(cls, prmtop_path):
        '''
        Get charge from the .prmtop file
        Take the (path) of .prmtop file and return a [list of charges] with corresponding to the atom sequence
        '''
        with open(prmtop_path) as f:
            
            charge_list=[]
            line_index=0

            for line in f:
                
                line_index=line_index+1 #current line
                
                if line.strip() == r'%FLAG POINTERS':
                    format_flag=line_index
                if line.strip() == r'%FLAG CHARGE':
                    charge_flag=line_index

                if 'format_flag' in dir():
                    if line_index == format_flag+2:
                        N_atom=int(line.split()[0])
                        del format_flag
                        
                if 'charge_flag' in dir():
                    if line_index >= charge_flag+2 and line_index <= charge_flag+1+ceil(N_atom/5):
                        for i in line.strip().split():
                            charge_list.append(float(i)/18.2223)
        return charge_list



# 重写conf类
# 
# 写修复的方法Rosetta优先 // 与uniport的对比
# 用seq重写随机突变的方法（flag的存储，随机的方式，突变的实施）

#htmd的不足
#1.结构修复 （只做到保留残基序号从而保留缺失片段的位置）
#2.金属中心附近的质子态 （可以保留金属离子，但是质子态没有处理） 

# func outside of the class
def get_PDB(name):
    '''
    connect to the database
    '''
    pass


def PDB_to_AMBER_PDB(path):
    '''
    Make the file convertable with tleap without error
    - Test result: The header part cause duplication of the residues. Deleting that part may give normal tleap output
    - Test result: For some reason, some ligand will miss if directly covert after simple header cutting
    - Test result: `cat 1NVG.pdb |grep "^ATOM\|^HETATM\|^TER|^END" > 1NVG-grep.pdb` will be fine
    - WARNINGs
    '''
    pass


#TestOnly
a = PDB('1Q4T_grep_rmW_aH_ffsol.pdb')
a.layer_preset=2
# a.layer_atoms=['4231-4422', '1-4230,4423-40780']
a.PDB2QMMM(keywords='test', prmtop_path='./1Q4T_grep_rmW_aH.prmtop')
# a._get_oniom_layer()
