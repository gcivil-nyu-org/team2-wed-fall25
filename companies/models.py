from django.db import models
from django.conf import settings
import os


def company_document_upload_path(instance, filename):
    """Generate upload path for company documents"""
    return f'companies/{instance.company.slug}/{instance.content_type.lower()}/{filename}'


class Company(models.Model):
    """Company model for storing company information"""
    slug = models.SlugField(max_length=50, unique=True, help_text='Company identifier (e.g., amazon, google)')
    name = models.CharField(max_length=100, help_text='Display name')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CompanyDocument(models.Model):
    """Stores company-specific content PDFs for RAG pipeline"""
    CONTENT_TYPE_CHOICES = (
        ('CODING', 'Coding Questions'),
        ('BEHAVIORAL', 'Behavioral Questions'),
        ('SYSTEM_DESIGN', 'System Design Questions'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    file = models.FileField(upload_to=company_document_upload_path)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    num_chunks = models.IntegerField(default=0, help_text='Number of chunks created')
    error_message = models.TextField(blank=True, help_text='Error details if failed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'content_type']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.content_type} - {self.get_status_display()}"


class CompanyChunk(models.Model):
    """Stores text chunks for company-specific interview content"""
    document = models.ForeignKey(
        CompanyDocument,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    content_type = models.CharField(max_length=20, choices=CompanyDocument.CONTENT_TYPE_CHOICES)
    text = models.TextField(help_text='The actual text content')
    metadata = models.JSONField(default=dict, help_text='Additional metadata (page_num, chunk_index, etc.)')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document', 'id']
        indexes = [
            models.Index(fields=['company', 'content_type']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.content_type} - Chunk {self.id}"
