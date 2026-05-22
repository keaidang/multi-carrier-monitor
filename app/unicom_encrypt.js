// unicom_encrypt.js
// Mock window and navigator for Barrett rsa.js
global.window = global;
global.navigator = { userAgent: "Mozilla/5.0" };

const fs = require('fs');
const path = require('path');

// Load rsa.js from the same directory
const rsaPath = path.join(__dirname, 'rsa.js');
const rsaCode = fs.readFileSync(rsaPath, 'utf8');
eval(rsaCode);

// Retrieve password from command line
const args = process.argv.slice(2);
const plainPassword = args[0] || "";

// Exponent and Modulus
const modulus = "82fd84c464ab864897660ec64bafc32b998b60d5713dd57177820da7cf2409836b4506aa5c2b2943e701b6810df16da0b47e96274765aaf2d72152c5ca76d796756ec8c496cf4365c350c52312368e0c8c5504a14b1122bbde9c0f05627f33eb05ad52ea1f2c8ca7cf6a68e4ee9eee6b45773dc11fe830778202c8209d2ffaab";

const key = RSAUtils.getKeyPair("11", "", modulus);

// 1. Base64 encode the password
const testPasswordBase64 = Buffer.from(plainPassword).toString('base64');

// 2. Encrypt
const encrypted = RSAUtils.encryptedString(key, testPasswordBase64);
process.stdout.write(encrypted);
