#!/usr/bin/env python3
"""
Generate the encrypted credential blob a portal card stores.

Each card's Launch button carries the *site* password encrypted under the
*portal master* password. The browser decrypts it in `decryptPassword()`
(index.html) once the visitor has entered the master, so the site passwords are
never sitting in the page as plaintext.

The scheme, mirrored exactly from index.html:

    PBKDF2-HMAC-SHA256(master, salt, 100_000 iterations) -> 32-byte key
    AES-256-GCM(key, iv) -> ciphertext
    blob = base64(salt[16] || iv[12] || ciphertext)

Usage:
    python3 encrypt_password.py 'WSJ$2026'
    python3 encrypt_password.py 'WSJ$2026' --master ICF2026
    python3 encrypt_password.py --verify '<blob>'      # round-trip an existing card

Paste the printed blob as the second argument of launch() on the card:

    <button class="btn-launch"
      onclick="launch('https://.../#about','<blob>')">Launch</button>

Quote the password in the shell -- '$' and '!' are otherwise eaten by zsh.
"""

import argparse
import base64
import getpass
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 100_000
SALT_LEN = 16
IV_LEN = 12


def derive(master: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", master.encode(), salt, ITERATIONS, 32)


def encrypt(site_password: str, master: str) -> str:
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    ct = AESGCM(derive(master, salt)).encrypt(iv, site_password.encode(), None)
    return base64.b64encode(salt + iv + ct).decode()


def decrypt(blob: str, master: str) -> str:
    raw = base64.b64decode(blob)
    salt, iv, ct = raw[:SALT_LEN], raw[SALT_LEN:SALT_LEN + IV_LEN], raw[SALT_LEN + IV_LEN:]
    return AESGCM(derive(master, salt)).decrypt(iv, ct, None).decode()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("password", nargs="?", help="the site password to encrypt")
    ap.add_argument("--master", help="portal master password (prompted if omitted)")
    ap.add_argument("--verify", metavar="BLOB",
                    help="decrypt an existing blob instead, to check the master")
    args = ap.parse_args()

    master = args.master or getpass.getpass("Portal master password: ")

    if args.verify:
        print(decrypt(args.verify, master))
        return

    if not args.password:
        ap.error("give a site password to encrypt, or --verify a blob")

    blob = encrypt(args.password, master)
    # Never emit a blob without proving it round-trips; a card carrying a bad
    # blob fails only at the moment someone tries to use it.
    assert decrypt(blob, master) == args.password, "round-trip failed"
    print(blob)


if __name__ == "__main__":
    main()
