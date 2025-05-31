const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser')
const app = express();
const PORT = 5000;

app.use(cors());
app.use(bodyParser.json());

app.get('/', (req,res) => {res.send('Backend is running');
});

app.post('/login',(req,res)=>{
    const {username, password} = req.body;

    if(username === 'admin' && password === 'password'){
        res.json({success:true, username:'admin'});
    } 
    else {
        res.json({success:false, message:'invalide credentials'})
    }
});

app.listen(PORT, ()=>{
    console.log(`Server is running on http://localhost:${PORT}`);
});
