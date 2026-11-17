// Runs only when the research volume is initialized.
db.getSiblingDB('var_research').createUser({
  user: 'research_writer',
  pwd: process.env.RESEARCH_APP_PASSWORD,
  roles: [{ role: 'readWrite', db: 'var_research' }],
});
const research = db.getSiblingDB('var_research');
research.createCollection('notes', { validator: { $jsonSchema: {
  bsonType: 'object', required: ['title', 'body', 'sourceUrl', 'createdAt', 'updatedAt', 'revision'],
  properties: {
    title: { bsonType: 'string', minLength: 1, maxLength: 150 },
    body: { bsonType: 'string', minLength: 1, maxLength: 10000 },
    sourceUrl: { bsonType: 'string', pattern: '^https://' },
    revision: { bsonType: ['int', 'long'], minimum: 1 },
    createdAt: { bsonType: 'date' }, updatedAt: { bsonType: 'date' },
  },
} } });
research.notes.createIndex({ updatedAt: -1 });
