{
  description = "CardStream: Payments Platform Analytics ETL & Dashboard";

  # flake.lock pins nixpkgs rev — same hash = byte-for-byte identical
  # environment. Run `nix flake lock` to update; never commit without lock.
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs =
    { flake-parts, ... }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];

      perSystem =
        { pkgs, lib, ... }:
        {
          devShells.default = pkgs.mkShell {
            packages =
              [
                pkgs.python311
                pkgs.uv
                pkgs.git
                pkgs.gnumake
                pkgs.ruff
                pkgs.postgresql
                pkgs.sops
                pkgs.age
              ]
              ++ lib.optionals pkgs.stdenv.isLinux [
                pkgs.stdenv.cc.cc.lib
                pkgs.zlib
              ]
              ++ lib.optionals pkgs.stdenv.isDarwin [
                pkgs.darwin.apple_sdk.frameworks.Security
                pkgs.darwin.apple_sdk.frameworks.SystemConfiguration
              ];

            shellHook = ''
              if [ ! -d .venv ]; then
                echo "📦 Creating Python venv with uv..."
                uv sync --extra dev --extra postgresql
              fi
              source .venv/bin/activate
              export PYTHONPATH="$PWD/src:$PYTHONPATH"
              export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:$LD_LIBRARY_PATH"

              # Decrypt secrets if available; fall back to defaults for first-time setup
              if [ -f secrets.yaml ]; then
                eval "$(sops --decrypt --output-type dotenv secrets.yaml 2>/dev/null \
                  | sed 's/=\(.*\)/="\1"/' \
                  | sed 's/^/export /')" \
                  && echo "🔐 Secrets loaded from secrets.yaml"
              else
                export PGHOST="/tmp/cardstream-pg"
                export PGPORT="5433"
                export DATABASE_URL="postgresql:///cardstream?host=/tmp/cardstream-pg&port=5433"
                echo "⚠️  No secrets.yaml — using defaults (run: sops secrets.yaml)"
              fi
              # PGDATA must be absolute — always set after secrets load
              export PGDATA="$PWD/.pgdata"

              echo "✨ CardStream devShell activated"
              echo "Python: $(python --version)"
              echo "uv: $(uv --version)"
              echo "PostgreSQL: $(psql --version | head -1)"
            '';
          };
        };
    };
}
