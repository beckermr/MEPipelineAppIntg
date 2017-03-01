import distutils
from distutils.core import setup
import glob

bin_files = glob.glob("bin/*") 

# The main call
setup(name='mepipelineappintg',
      version ='1.1.6',
      license = "GPL",
      description = "A set python utils apps for the DES multiepoch pipeline",
      author = "Michelle Gower",
      author_email = "mgower@illinois.edu",
      packages = ['mepipelineappintg'],
      package_dir = {'': 'python'},
      scripts = bin_files,
      data_files=[('ups',['ups/MEPipelineAppIntg.table'])],
      )

