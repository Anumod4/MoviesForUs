import os
import sys
import importlib

def check_module(module_name):
    try:
        importlib.import_module(module_name)
        print(f"{module_name} is installed")
        return True
    except ImportError:
        print(f"{module_name} is NOT installed")
        return False

def main():
    print("Python Executable:", sys.executable)
    print("Python Version:", sys.version)
    print("Python Path:", sys.path)

    # Check critical modules
    modules_to_check = [
        'flask', 
        'flask_login', 
        'flask_sqlalchemy', 
        'flask_bcrypt',
        'werkzeug'
    ]

    for module in modules_to_check:
        check_module(module)

    # Check virtual environment
    print("\nVirtual Environment:")
    print("Is Virtual Env Active:", hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    
    # Check pip list
    print("\nInstalled Packages:")
    os.system(f"{sys.executable} -m pip list")

if __name__ == "__main__":
    main()
