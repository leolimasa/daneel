from daneel import *

def main():
    changed_files = ",".join(changed_git_files())
    claude_code(f'''
        Read the following files and search for comments starting with 'xxx' : {changed_files}. These comments indicate that the code needs to be fixed.
        For each comment starting with 'xxx', address the issue mentioned in the comment and remove the 'xxx' comment from the code.
    ''')

    validate("test.sh", fail_fn=lambda output: claude_code(f'''
        The implementation you provided did not pass the tests in test.sh. Here is the output from the failed tests:
        {output}
        Please fix the implementation so that all tests pass.
    ''')) 

if __name__ == "__main__":
    main()
