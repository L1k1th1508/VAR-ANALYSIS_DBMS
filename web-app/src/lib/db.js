import { Pool } from "pg";
import { MongoClient } from "mongodb";

// PostgreSQL Pool for reader access
export const pgPool = new Pool({
  connectionString:
    process.env.READER_DATABASE_URL ||
    "postgresql://app_reader:readerpass@127.0.0.1:55432/var_analytics",
});

// MongoDB Client
const mongoUri =
  process.env.MONGO_URI ||
  "mongodb://mongoadmin:mongopassword@127.0.0.1:27017/var_nosql?authSource=admin";

let cachedClient = null;

export async function getMongoDb() {
  if (!cachedClient) {
    cachedClient = new MongoClient(mongoUri);
    await cachedClient.connect();
  }
  return cachedClient.db("var_nosql");
}
