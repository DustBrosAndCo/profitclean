namespace DigitalSignage.Shared.Models;

public class Playlist
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public List<int> ContentIds { get; set; } = new();
    public string ScheduleJson { get; set; } = string.Empty; // For future scheduling
}