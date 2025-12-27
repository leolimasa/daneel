from ..daneel import *

def main():
    changed_files = ",".join(changed_git_files())

    claude_code(f'''
        Read the following files and search for comments starting with 'IMPLEMENT' : {changed_files}. These comments indicate that the function or code needs to be implemented. Implement the required functionality for each 'IMPLEMENT' comment and remove the 'IMPLEMENT' comment from the code. Create new functions or classes as needed to fulfill the requirements. Create unit tests for the implemented functionality if they do not already exist.
    ''')

    validate("test.sh", fail_fn=lambda output: claude_code(f'''
        The implementation you provided did not pass the tests in test.sh. Here is the output from the failed tests:
        {output}
        Please fix the implementation so that all tests pass.
    ''')) 
