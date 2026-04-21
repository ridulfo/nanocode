{
  description = "A minimal sandboxed local coding agent";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          nanocode = pkgs.python313Packages.buildPythonApplication rec {
            pname = "nanocode";
            version = "0.1.0";
            pyproject = true;

            src = ./.;

            build-system = [
              pkgs.python313Packages.hatchling
            ];

            propagatedBuildInputs = [
              pkgs.bubblewrap
            ];

            postInstall = ''
              mv $out/bin/nanocode $out/bin/.nanocode-unwrapped
              cp ${./nanocode-wrapper.sh} $out/bin/nanocode
              chmod +w $out/bin/nanocode
              substituteInPlace $out/bin/nanocode \
                --replace @bwrap@ ${pkgs.bubblewrap}/bin/bwrap \
                --replace @nanocode@ $out/bin/.nanocode-unwrapped
              chmod +x $out/bin/nanocode
            '';

            meta = with pkgs.lib; {
              description = "A minimal sandboxed local coding agent";
              homepage = "https://github.com/ridulfo/nanocode";
              license = licenses.gpl3Plus;
              mainProgram = "nanocode";
              platforms = platforms.unix;
            };
          };

          default = self.packages.${system}.nanocode;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            shellHook = "exec zsh";
            buildInputs = with pkgs; [
              python313
              bubblewrap
            ];
          };
        }
      );
    };
}
