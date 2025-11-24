// TODO: Your data models/structs go here
//
// Learning objectives:
// 1. Learn how to define structs in Rust
// 2. Understand derive macros (Debug, Serialize, Deserialize)
// 3. Practice mapping database rows to Rust types
// 4. Learn about Option<T> for nullable fields
//
// You need to create structs for:
// - PlayerStats (matches player_stats table)
// - PlayerShootingZone (matches player_shooting_zones table)
// - TeamDefensiveZone (matches team_defensive_zones table)
// - PlayerAssistZone (matches player_assist_zones table)
// - PlayerPlayType (matches player_play_types table)
//
// Example pattern:
// #[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
// pub struct PlayerStats {
//     pub player_id: i64,
//     pub player_name: String,
//     pub season: String,
//     pub points: Option<f64>,  // Use Option for nullable fields
//     // ... add all other fields from your schema
// }
//
// Tips:
// - Check your database schema carefully
// - Use appropriate Rust types (i64 for INTEGER, f64 for REAL, String for TEXT)
// - Remember to handle nullable columns with Option<T>
