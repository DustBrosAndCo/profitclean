namespace DigitalSignage.Shared.Models;

public class Device
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string DeviceType { get; set; } = string.Empty; // NUC, Pi5, Samsung, Cisco
    public string Location { get; set; } = string.Empty;   // Building / Room
    public string Status { get; set; } = "Offline";        // Online, Offline, Error
    public DateTime LastHeartbeat { get; set; }
    public string IpAddress { get; set; } = string.Empty;
    public string UniqueId { get; set; } = string.Empty;   // Unique identifier
}