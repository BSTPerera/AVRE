const express = require('express');
const helmet = require('helmet');
const app = express();
const path = require('path');

// SECURITY: Use Helmet to set Content Security Policy (CSP)
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'"], // Block inline scripts
            objectSrc: ["'none'"],
            upgradeInsecureRequests: [],
        },
    },
}));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static('public'));

app.get('/', (req, res) => {
    res.render('index', { query: null });
});

app.get('/search', (req, res) => {
    const q = req.query.q;
    // SECURITY: Input Validation (Simple check)
    if (q && q.length > 100) {
        return res.status(400).send("Query too long");
    }

    // FIX: Rendering using default EJS tags which escape HTML
    // The view uses <%= query %> which converts chars to entities
    res.render('index', { query: q });
});

const PORT = 3000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Fixed App running on port ${PORT}`);
});
