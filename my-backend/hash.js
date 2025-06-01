const bcrypt = require('bcrypt');

const plainPassword = 'test123'; // Change to any password you want
const saltRounds = 10;

bcrypt.hash(plainPassword, saltRounds, (err, hash) => {
  if (err) {
    console.error('Hashing failed:', err);
  } else {
    console.log('Hashed password:', hash);
  }
});
