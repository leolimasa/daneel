{
  description = "Daneel - Python helper functions for agentic coding assistants";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        python = pkgs.python311;
        
        pythonEnv = python.withPackages (ps: with ps; [
          # Core dependencies
          pyyaml
          # Testing
          pytest
          pytest-cov
          # Type checking
          mypy
          # Linting
          ruff
        ]);

        daneel = pkgs.stdenv.mkDerivation {
          name = "daneel";
          src = ./.;
          
          buildInputs = [ pythonEnv ];
          
          installPhase = ''
            mkdir -p $out/bin
            mkdir -p $out/lib/python
            
            # Copy the source file
            cp daneel.py $out/lib/python/
            
            # Create executable wrapper
            cat > $out/bin/daneel << EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, '$out/lib/python')
import daneel
EOF
            chmod +x $out/bin/daneel
          '';
        };

      in {
        packages = {
          default = daneel;
          daneel = daneel;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.uv
          ];
          
          shellHook = ''
            echo "Daneel development environment"
            echo "Python version: ${python.version}"
            echo "Available commands: python, pytest, mypy, ruff, uv"
          '';
        };
      });
}