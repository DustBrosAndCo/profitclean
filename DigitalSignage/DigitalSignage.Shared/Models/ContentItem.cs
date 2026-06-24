namespace DigitalSignage.Shared.Models;

public class ContentItem
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string FilePath { get; set; } = string.Empty;
    public string ContentType { get; set; } = string.Empty; // Image, Video, HTML, Widget
    public long FileSize { get; set; }
    public DateTime UploadDate { get; set; }
}