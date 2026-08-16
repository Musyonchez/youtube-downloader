const crypto = require('crypto');
const fs = require('fs');

const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
  modulusLength: 2048,
});

const pubDer = publicKey.export({ type: 'spki', format: 'der' });
const privPem = privateKey.export({ type: 'pkcs8', format: 'pem' });

// Chrome extension ID: SHA256 of the DER SPKI public key, take first 16
// bytes, map each nibble to a letter a-p (0->a ... 15->p).
const hash = crypto.createHash('sha256').update(pubDer).digest();
const first16 = hash.subarray(0, 16);
let id = '';
for (const byte of first16) {
  const hi = (byte >> 4) & 0xf;
  const lo = byte & 0xf;
  id += String.fromCharCode(97 + hi);
  id += String.fromCharCode(97 + lo);
}

const pubB64 = pubDer.toString('base64');

console.log('EXTENSION_ID=' + id);
console.log('PUBLIC_KEY_B64=' + pubB64);
fs.writeFileSync('dev_private_key.pem', privPem);
